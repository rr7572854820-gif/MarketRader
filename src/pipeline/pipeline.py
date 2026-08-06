"""The automation pipeline: Fetch -> Analyze -> Cluster -> Verify -> Report,
runnable as a single call.

This module is a library, not a CLI — it never calls print() (matching
every other orchestration-adjacent module in this project: Extractor,
Aggregator, and Verifier don't print either; only formatter.py and CLI
scripts do). Operational visibility is via the standard `logging`
module instead, so a caller (runner.py, or any future caller) decides
whether and how to display it. See src/pipeline/runner.py for the CLI.

Reliability design:
- Fetching gets its own retry loop (transient network/API failures) —
  AI calls already retry inside GeminiProvider (Task 3); this adds the
  one stage that didn't have retry before.
- Extraction failures are per-post: one bad post never aborts the run.
- Pipeline.run() has exactly one broad `except Exception` — deliberately,
  as the single top-level safety net for the one place in this codebase
  whose entire job is "never crash, always return a summary." Every
  other module in this project uses specific exception types; this is
  the one place a catch-all is the right call, not the anti-pattern of
  swallowing errors quietly — every caught error is recorded in
  PipelineExecutionSummary.errors, never silently dropped.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from src.ai import get_ai_provider
from src.ai.base import AIProvider
from src.config import Config, load_config
from src.fetchers import FetcherError, get_fetcher
from src.fetchers.base import Fetcher
from src.insights.aggregator import Aggregator
from src.insights.extractor import Extractor
from src.insights.models import DiscussionInsight, OpportunityCluster
from src.models import FetchedPost, FetchQuery
from src.pipeline.cache import CachingAIProvider, ResponseCache
from src.reporting.formatter import save_markdown_file
from src.reporting.models import InsightReport
from src.reporting.report_generator import generate_report
from src.search.query_expander import QueryExpander
from src.verification.models import VerificationReport
from src.verification.verifier import Verifier

logger = logging.getLogger(__name__)

# (stage, message, percent) - stage is one of "fetch"/"analyze"/
# "cluster"/"verify"/"report"/"done"; percent is 0-100, non-decreasing
# across one run() call. Optional and purely additive: run() behaves
# identically whether or not a caller passes one. No SSE, no HTTP, no
# frontend wiring - see Pipeline.run()'s on_progress parameter.
ProgressCallback = Callable[[str, str, int], None]

_FETCH_MAX_ATTEMPTS = 3
_FETCH_BASE_DELAY_SECONDS = 1.0

# Sources with no community/subreddit concept - a keyword is their
# entire search query (GitHubFetcher's Search Issues call, HNFetcher's
# Algolia call), and both support num_reports-driven oversampling the
# same way. Reddit is deliberately excluded: its keyword is an optional
# post-fetch filter over a chosen subreddit, not the whole query, so
# num_reports/oversampling has no equivalent meaning there. "all" (see
# _MULTI_SOURCE_EXPANSION) is included - it's github+hackernews fetched
# together, so the same keyword-driven/oversample-eligible reasoning
# applies to the combined run as a whole.
_KEYWORD_DRIVEN_SOURCES = ("github", "hackernews", "hn", "all")

# What source="all" actually fetches from, in parallel (_fetch_all_sources).
# Reddit is deliberately excluded from this expansion even though it's a
# real source - it has its own optional-keyword/subreddit-targeted
# semantics (see _KEYWORD_DRIVEN_SOURCES above) that don't combine
# cleanly with GitHub/Hacker News's keyword-is-the-whole-query model,
# and (unlike them) it has a working mock fallback that a "combine every
# source" run would need to special-case around for no clear benefit.
_MULTI_SOURCE_EXPANSION = ("github", "hackernews")

# Proper brand capitalization for the "all"-source progress message
# (run()) - "github".title()/"hackernews".title() would produce
# "Github"/"Hackernews", not "GitHub"/"Hacker News".
_SOURCE_DISPLAY_NAMES = {"github": "GitHub", "hackernews": "Hacker News", "hn": "Hacker News"}

# GitHub/Hacker News-only report-count reliability (PipelineConfig.num_reports):
# calculate_fetch_limit() decides how many discussions to request on
# the first fetch for a given number of requested reports. Not every
# discussion survives extraction/verification/dedup into a distinct
# cluster, so the first fetch deliberately over-requests - by a
# multiplier that shrinks as the request grows, since the *relative*
# oversampling headroom needed to reliably clear N valid clusters
# doesn't scale linearly with N. Pipeline.run() allows exactly one
# further fetch round beyond that (by construction -
# _oversample_for_report_count has exactly one call site, not a loop)
# before honestly returning fewer than requested. An unbounded retry
# loop would risk exactly the runaway AI-provider cost / GitHub
# rate-limit exposure that post_limit's own 100-item API-layer cap
# (see src/api/models.py) exists to prevent - post_limit remains the
# absolute ceiling in every case; calculate_fetch_limit()'s own
# _FETCH_LIMIT_HARD_CAP (200) is a second, independent ceiling on top
# of that, relevant only when PipelineConfig is constructed directly
# (CLI/tests) with a num_reports value the API layer itself could
# never produce (capped at 100 there).
_FETCH_LIMIT_HARD_CAP = 200


def calculate_fetch_limit(requested: int) -> int:
    """Adaptive oversampling based on request size.

    Always fetches more than requested to guarantee N verified reports
    after quality filtering. Never fetches so many that it hits API
    limits or causes unacceptable response times - the multiplier
    shrinks as `requested` grows (3x for small requests down to 1.1x
    for large ones), and _FETCH_LIMIT_HARD_CAP (200) is an absolute
    ceiling no request can push past.

    Raises:
        ValueError: If requested < 1 - there is nothing meaningful to
            oversample for a non-positive report count.
    """
    if requested < 1:
        raise ValueError("Limit must be at least 1")

    if requested <= 10:
        multiplier, hard_cap = 3.0, 30
    elif requested <= 30:
        multiplier, hard_cap = 2.0, 60
    elif requested <= 50:
        multiplier, hard_cap = 1.5, 75
    elif requested <= 100:
        multiplier, hard_cap = 1.25, 125
    else:
        multiplier, hard_cap = 1.1, _FETCH_LIMIT_HARD_CAP

    calculated = int(requested * multiplier)
    return min(calculated, hard_cap)


@dataclass(frozen=True)
class PipelineConfig:
    """Every configuration option requirement 3 named.

    Attributes:
        subreddit: Passed through as FetchQuery.community when
            source="reddit" (the default). Ignored by the mock fetcher,
            but still required by argparse/AnalyzeRequest for clarity
            about what a real run would target.
        source: Which Fetcher to use - "reddit" (default), "github",
            "hackernews" (alias "hn"), or "all" (GitHub + Hacker News
            fetched simultaneously, results merged/deduplicated before
            analysis - see run()'s own _fetch_all_sources()). Every
            value except "all" is passed straight through to
            get_fetcher()'s own source parameter (src/fetchers/__init__.py,
            unchanged - "all" is expanded into _MULTI_SOURCE_EXPANSION
            and fetched via one get_fetcher() call per real source
            instead, since the factory itself has no "all" concept).
        keyword: For Reddit, an optional keyword filter, passed
            through unchanged. Required (not optional) when
            source="github": GitHubFetcher takes no repo at all, and
            this value drives its entire GitHub Search Issues API
            query. Unlike Reddit's keyword, this one is never passed
            to GitHubFetcher verbatim - run() first sends it through
            src.search.query_expander.QueryExpander (using this run's
            own AI provider) to turn free-text, natural-language input
            (e.g. "problems with invoice automation") into several
            related short technical search terms (e.g. "invoicing
            saas", "billing automation tool"). All of them reach
            GitHubFetcher via FetchQuery.keywords (src/models.py) -
            it searches each one separately and merges/ranks the
            combined results (see github_fetcher.py's _discover_issues)
            - while FetchQuery.keyword still carries just the first
            term, for any other fetcher that only understands a single
            keyword. AnalyzeRequest enforces the "required for
            github" rule at the API layer; the CLI has no --source
            flag yet (see ENGINEERING_GUIDE.md's known limitations).
        post_limit: Max posts to fetch. Remains the hard ceiling on
            total discussions ever fetched in one run, even when
            num_reports is set - see num_reports below.
        num_reports: Desired number of final opportunity reports. Only
            meaningful when source="github" - ignored otherwise
            (Reddit's fetch mechanism doesn't support the same
            oversample-and-retry approach; see pipeline.py's
            _initial_fetch_limit). When set: the first fetch requests
            calculate_fetch_limit(num_reports) discussions rather than
            post_limit outright - a tiered multiplier (3x for small
            requests down to 1.1x for large ones, absolute-capped at
            200) rather than a flat multiple, still never exceeding
            post_limit; if still short of num_reports clusters
            afterward, one further fetch up to post_limit is made
            before giving up; and the final report's top_opportunities
            is capped to exactly num_reports entries (top-ranked -
            Aggregator already sorts by score), while project_health
            and the executive summary still describe everything
            actually analyzed, not just the capped slice (though
            PipelineExecutionSummary.clusters_found does reflect the
            capped, delivered count - see run()'s summary construction).
            Returning fewer than num_reports is expected and correct, not an
            error, whenever post_limit or genuinely-available
            discussions run out first - this never fabricates
            additional reports to hit the requested count.
        output_dir: Where the Markdown report and the pipeline
            execution summary JSON get saved.
        ai_provider: "auto" (default — real Gemini if GEMINI_API_KEY
            is set, mock otherwise, matching every other command in
            this project) or "mock" (force mock regardless of config).
            There is no "gemini" option: forcing real Gemini when it
            isn't configured wouldn't do anything "auto" doesn't
            already do when it *is* configured, so a third option
            would add a choice without adding a capability.
        report_format: "terminal", "markdown", or "both".
        force_mock_fetch: True forces MockFetcher regardless of Reddit
            config. Set together with ai_provider="mock" by --mock in
            the CLI for a single "run this fully offline" switch.
        cache_enabled: Task 8. When True (default), AI provider
            responses are cached by prompt hash — re-running the
            pipeline over overlapping data skips real API calls for
            anything already seen, which matters given how easily the
            Gemini free-tier daily quota gets exhausted (see
            SESSION.md). Only JSON-shaped responses are cached, so
            Extractor's own retry-on-malformed-JSON always gets a
            fresh call — see src/pipeline/cache.py for why.
        cache_path: Where the cache file lives. Relative by default,
            consistent with output_dir's existing convention (both are
            resolved relative to the current working directory, not
            anchored to the project root).
    """

    subreddit: str = "all"
    source: str = "reddit"
    keyword: Optional[str] = None
    post_limit: int = 25
    num_reports: Optional[int] = None
    output_dir: Path = Path("output")
    ai_provider: str = "auto"
    report_format: str = "both"
    force_mock_fetch: bool = False
    cache_enabled: bool = True
    cache_path: Path = Path(".cache") / "ai_responses.json"


@dataclass(frozen=True)
class PipelineExecutionSummary:
    """Requirement 5's logging fields, as a saveable, testable record —
    not just log lines. See pipeline.py's save location:
    output_dir/pipeline_run_<timestamp>.json.

    cache_hits/cache_misses (Task 8): both 0 when cache_enabled=False.
    ai_calls_made only counts real API calls (cache misses) — a cache
    hit means no real call happened, so it must never inflate this
    number; see _CountingAIProvider/CachingAIProvider wiring order in
    Pipeline.run() for why that's guaranteed, not just documented.
    """

    start_time: datetime
    end_time: datetime
    duration_seconds: float
    posts_fetched: int
    posts_analyzed: int
    ai_calls_made: int
    cache_hits: int
    cache_misses: int
    clusters_found: int
    errors: List[str]
    report_path: Optional[Path]
    succeeded: bool


@dataclass(frozen=True)
class PipelineRunResult:
    """What Pipeline.run() returns: the execution summary, plus the
    actual InsightReport if one was produced (None only in the total-
    failure case where generate_report itself never ran).
    """

    summary: PipelineExecutionSummary
    report: Optional[InsightReport]


class _CountingAIProvider(AIProvider):
    """Wraps any AIProvider and counts calls to generate_text.

    Implements the AIProvider interface itself rather than modifying
    GeminiProvider/MockAIProvider or the interface — a pure decorator,
    transparent to Extractor and Aggregator, which both already accept
    "any AIProvider" and have no idea this wrapping happened.

    call_count is incremented under a lock: Extractor.extract_all_parallel()
    calls generate_text() from multiple worker threads within one
    Pipeline.run(), and a bare `+= 1` is not guaranteed atomic across
    threads (load-add-store, not a single bytecode op) - without this,
    ai_calls_made could undercount under real concurrent access.
    """

    def __init__(self, wrapped: AIProvider) -> None:
        self._wrapped = wrapped
        self._lock = threading.Lock()
        self.call_count = 0

    def check_connection(self) -> None:
        self._wrapped.check_connection()

    def generate_text(self, prompt: str) -> str:
        with self._lock:
            self.call_count += 1
        return self._wrapped.generate_text(prompt)


class Pipeline:
    """Runs the full Fetch -> Analyze -> Cluster -> Verify -> Report
    sequence for one PipelineConfig.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._config = config

    def _emit(self, on_progress: Optional[ProgressCallback], stage: str, message: str, percent: int) -> None:
        if on_progress:
            on_progress(stage, message, percent)

    def run(self, on_progress: Optional[ProgressCallback] = None) -> PipelineRunResult:
        """Runs the pipeline. on_progress, if given, is called at each
        major stage transition with (stage, message, percent) - purely
        observational, optional, and never affects what the run
        actually does; a caller that passes nothing gets identical
        behavior to before this parameter existed.

        Not fired for GitHub's fetch internals specifically (repo
        discovery / per-repo issue counts): GitHubFetcher no longer has
        a repo-discovery step or a per-repo loop at all (see its own
        module docstring - replaced by a single Search Issues API call
        across all of GitHub), so there is no real per-repo progress
        for run() to observe here without threading a callback through
        GitHubFetcher's own fetch() signature (and the shared Fetcher
        interface) - out of this method's scope. Only fetch() start/end
        are reported, honestly, from what run() actually knows.

        Only the first (main) fetch/analyze/cluster pass reports
        progress - a GitHub num_reports oversample round (see
        _oversample_for_report_count), when it happens, does not, so
        that percent stays non-decreasing within one run() call rather
        than resetting partway through a rare, variable-length retry.
        """
        start_time = datetime.now(timezone.utc)
        errors: List[str] = []
        posts: List[FetchedPost] = []
        insights: List[DiscussionInsight] = []
        clusters: List[OpportunityCluster] = []
        ai_calls_made = 0
        cache_hits = 0
        cache_misses = 0
        report_path: Optional[Path] = None
        insight_report: Optional[InsightReport] = None
        succeeded = True

        try:
            app_config = load_config()
            # source="all" has no single fetcher to build up front - see
            # _active_sources()/_fetch_all_sources(). force_mock collapses
            # back to a single (mock) source regardless, since get_fetcher()
            # always returns MockFetcher when force_mock=True no matter
            # what source is passed.
            active_sources = self._active_sources()
            is_multi_source = len(active_sources) > 1
            ai_provider, ai_provider_label = _resolve_ai_provider_and_label(self._config, app_config)

            # Layering matters: counting must be *inside* caching, so a
            # cache hit never reaches (and never increments) the call
            # counter — ai_calls_made must reflect real API usage only.
            counting_provider = _CountingAIProvider(ai_provider)
            active_provider: AIProvider = counting_provider
            caching_provider: Optional[CachingAIProvider] = None
            if self._config.cache_enabled:
                cache = ResponseCache(self._config.cache_path)
                caching_provider = CachingAIProvider(counting_provider, cache)
                active_provider = caching_provider

            # Natural-language query expansion (GitHub and "all" runs,
            # since "all" includes GitHub - see _MULTI_SOURCE_EXPANSION):
            # a user's free-text description ("problems with invoice
            # automation") isn't itself a usable Search Issues query -
            # see src/search/query_expander.py. QueryExpander replaced
            # src.insights.keyword_extraction.extract_search_terms as
            # this run's mechanism for deriving search terms (that
            # module is left in place, unused on this path, not deleted
            # - see TODO.md) specifically to avoid making two separate
            # AI calls. All of QueryExpander's related terms are passed
            # to GitHubFetcher via FetchQuery.keywords (src/models.py) -
            # it searches each one separately and merges/ranks the
            # combined results (src/fetchers/github_fetcher.py's
            # _discover_issues); search_keyword (expanded_terms[0])
            # still goes in FetchQuery.keyword too, both as the primary
            # term for ranking/error messages and so any other fetcher
            # that only understands a single keyword is unaffected.
            # Uses the same counted/cached active_provider as every
            # other AI call this run makes, so ai_calls_made/cache
            # accounting stays accurate and a repeated identical
            # description is a cache hit, not a fresh billed call.
            # Expanded exactly once and reused for both the initial
            # fetch and any oversample round below - re-expanding per
            # round would risk a different (non-deterministic) query
            # fragmenting what should be one consistent search.
            search_keyword = self._config.keyword
            expanded_terms: Optional[List[str]] = None
            if self._config.source in ("github", "all") and self._config.keyword:
                expanded_terms = QueryExpander(active_provider).expand(self._config.keyword)
                search_keyword = expanded_terms[0]
                logger.info("Query expanded from %r to: %s", self._config.keyword, expanded_terms)

            # GitHubFetcher/HNFetcher both ignore FetchQuery.community
            # entirely (search is keyword-driven - see github_fetcher.py
            # /hn_fetcher.py); the keyword is passed here too only so log
            # lines naming "community" print something meaningful.
            community = (
                search_keyword or "" if self._config.source in _KEYWORD_DRIVEN_SOURCES else self._config.subreddit
            )
            initial_limit = self._initial_fetch_limit()
            if self._config.source in _KEYWORD_DRIVEN_SOURCES and self._config.num_reports:
                logger.info(
                    "User requested %d report(s). Fetching %d discussion(s) to guarantee quality after verification.",
                    self._config.num_reports,
                    initial_limit,
                )
                if self._config.num_reports > _FETCH_LIMIT_HARD_CAP:
                    logger.warning(
                        "Large request (%d reports). Fetching maximum %d discussions. Consider splitting "
                        "into smaller requests for faster results.",
                        self._config.num_reports,
                        _FETCH_LIMIT_HARD_CAP,
                    )
            query = FetchQuery(community=community, keyword=search_keyword, keywords=expanded_terms, limit=initial_limit)

            fetcher: Optional[Fetcher] = None
            if is_multi_source:
                source_labels = " + ".join(_SOURCE_DISPLAY_NAMES.get(s, s) for s in active_sources)
                self._emit(on_progress, "fetch", f"🔍 Searching {source_labels} for '{search_keyword}'...", 5)
            elif self._config.source == "github":
                self._emit(on_progress, "fetch", f"🔍 Searching GitHub for '{search_keyword}'...", 5)
            elif self._config.source in ("hackernews", "hn"):
                self._emit(on_progress, "fetch", f"🔍 Searching Hacker News for '{search_keyword}'...", 5)
            else:
                self._emit(on_progress, "fetch", f"🔍 Fetching discussions from {community}...", 5)
            fetch_start = time.time()
            if is_multi_source:
                posts = self._fetch_all_sources(app_config, active_sources, query, errors)
            else:
                fetcher = get_fetcher(app_config, source=active_sources[0], force_mock=self._config.force_mock_fetch)
                posts = self._fetch(fetcher, query, errors)
            fetch_time = time.time() - fetch_start
            logger.info("⏱ Fetch: %.1fs", fetch_time)
            self._emit(on_progress, "fetch", f"✅ Fetched {len(posts)} real discussions", 35)

            extract_start = time.time()
            insights = self._analyze(posts, active_provider, errors, on_progress)
            extract_time = time.time() - extract_start
            logger.info("⏱ Extract: %.1fs", extract_time)

            cluster_start = time.time()
            clusters = self._cluster(insights, active_provider, errors, on_progress)
            cluster_time = time.time() - cluster_start
            logger.info("⏱ Cluster: %.1fs", cluster_time)

            logger.info("⏱ Total: %.1fs", fetch_time + extract_time + cluster_time)

            if self._should_oversample(clusters, initial_limit):
                # No on_progress here - see run()'s own docstring on why
                # only the main pass reports progress.
                if is_multi_source:
                    posts, insights, clusters = self._oversample_for_report_count_multi(
                        app_config, active_sources, community, search_keyword, expanded_terms, posts,
                        len(clusters), active_provider, errors,
                    )
                else:
                    assert fetcher is not None  # set above whenever not is_multi_source
                    posts, insights, clusters = self._oversample_for_report_count(
                        fetcher, community, search_keyword, expanded_terms, posts, len(clusters), active_provider, errors
                    )

            verification_report = self._verify(insights, posts, on_progress)
            ai_calls_made = counting_provider.call_count
            if caching_provider is not None:
                cache_hits = caching_provider.hits
                cache_misses = caching_provider.misses

            self._emit(on_progress, "report", "📝 Generating final report...", 95)
            insight_report = generate_report(clusters, verification_report, posts, ai_provider_label)
            if self._config.source in _KEYWORD_DRIVEN_SOURCES and self._config.num_reports:
                if len(insight_report.top_opportunities) < self._config.num_reports:
                    logger.info(
                        "Note: Only %d of %d requested reports passed quality verification. "
                        "Showing best available results.",
                        len(insight_report.top_opportunities),
                        self._config.num_reports,
                    )
                # Cap the surfaced deliverable to exactly what was
                # requested, top-ranked first (Aggregator already
                # sorts by score - see its aggregate()) - but only
                # top_opportunities. project_health and the executive
                # summary still describe the full analysis actually
                # performed (all clusters found from all discussions
                # fetched), not just the surfaced slice - truncating
                # those too would misreport how much evidence the run
                # actually looked at.
                insight_report = replace(
                    insight_report, top_opportunities=insight_report.top_opportunities[: self._config.num_reports]
                )
            report_path = self._save_outputs(insight_report, start_time)

        except Exception as exc:  # noqa: BLE001 — deliberate top-level safety net, see module docstring
            logger.exception("Unexpected pipeline failure")
            errors.append(f"Unexpected pipeline failure: {type(exc).__name__}: {exc}")
            succeeded = False

        end_time = datetime.now(timezone.utc)
        summary = PipelineExecutionSummary(
            start_time=start_time,
            end_time=end_time,
            duration_seconds=(end_time - start_time).total_seconds(),
            posts_fetched=len(posts),
            posts_analyzed=len(insights),
            ai_calls_made=ai_calls_made,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            # len(insight_report.top_opportunities), not len(clusters):
            # identical for every run except a GitHub num_reports run,
            # where top_opportunities is deliberately capped to what
            # was requested (see above) - this summary stat reflects
            # what's actually delivered, while
            # InsightReport.project_health.total_opportunity_clusters
            # (inside the report body itself) still reports the full,
            # uncapped analysis breadth. insight_report is only None in
            # the total-failure case, where clusters is already [].
            clusters_found=len(insight_report.top_opportunities) if insight_report is not None else len(clusters),
            errors=errors,
            report_path=report_path,
            succeeded=succeeded,
        )
        self._save_summary(summary, start_time)
        logger.info(
            "Pipeline finished in %.1fs: %d posts fetched, %d analyzed, %d AI calls "
            "(%d cache hits, %d misses), %d clusters, %d error(s).",
            summary.duration_seconds,
            summary.posts_fetched,
            summary.posts_analyzed,
            summary.ai_calls_made,
            summary.cache_hits,
            summary.cache_misses,
            summary.clusters_found,
            len(summary.errors),
        )
        # Fires unconditionally, even on a failed run (succeeded=False)
        # - a progress UI should always get a terminal event so it
        # knows the run has actually finished, not hung; num_opportunities
        # is honestly 0 whenever insight_report was never produced.
        num_opportunities = len(insight_report.top_opportunities) if insight_report is not None else 0
        self._emit(
            on_progress,
            "done",
            f"🎉 Done! Found {num_opportunities} opportunities in {summary.duration_seconds:.1f}s",
            100,
        )
        return PipelineRunResult(summary=summary, report=insight_report)

    def _initial_fetch_limit(self) -> int:
        """post_limit for every run except a GitHub/Hacker News run with
        num_reports set, where the first fetch instead requests
        calculate_fetch_limit(num_reports) discussions - never more
        than post_limit, which stays the hard ceiling regardless of
        what calculate_fetch_limit's own tiered multiplier/cap would
        otherwise allow.
        """
        if self._config.source in _KEYWORD_DRIVEN_SOURCES and self._config.num_reports:
            return min(calculate_fetch_limit(self._config.num_reports), self._config.post_limit)
        return self._config.post_limit

    def _active_sources(self) -> List[str]:
        """Which real source(s) this run actually fetches from.

        source="all" expands to _MULTI_SOURCE_EXPANSION (GitHub + Hacker
        News, both keyword-driven and credential-free) fetched in
        parallel - see _fetch_all_sources(). force_mock collapses this
        back to a single-item list even when source="all", since
        get_fetcher() always returns Reddit's MockFetcher when
        force_mock=True regardless of what source it's given (there is
        no per-source mock variant to combine) - matching the
        dashboard's own "no mock equivalent" handling for GitHub/Hacker
        News/All Sources.
        """
        if self._config.source == "all" and not self._config.force_mock_fetch:
            return list(_MULTI_SOURCE_EXPANSION)
        return [self._config.source]

    def _split_limit(self, total_limit: int, num_sources: int) -> int:
        """Divides a combined fetch target evenly across multiple
        sources (source="all" only) - e.g. a combined target of 30
        discussions across 2 sources means each source's own
        FetchQuery.limit becomes 15, so the two sources' results sum
        back to roughly the original combined target instead of each
        independently fetching the full amount (which would roughly
        double the effective oversampling and API load).
        """
        return max(1, total_limit // num_sources)

    def _fetch_from_source(
        self, source: str, app_config: Config, query: FetchQuery, errors: List[str]
    ) -> List[FetchedPost]:
        """Fetches from exactly one source, in isolation - never raises.

        FetcherError is already handled by self._fetch() (retries, then
        records to `errors` and returns [] on final failure); the
        try/except here only guards against something self._fetch()
        itself doesn't expect (e.g. a bug inside get_fetcher() or a
        fetcher's own internals), so that - this runs inside a
        ThreadPoolExecutor worker, via _fetch_all_sources() - one
        source's unexpected failure can never prevent collecting
        another source's real results. Same per-item isolation
        precedent as BaseFetcher.fetch_parallel's own safe_fetch
        wrapper (src/fetchers/base.py) - not a new violation of
        "exactly one broad except Exception" (ENGINEERING_GUIDE.md
        §13): that claim was already inaccurate before this change
        (fetch_parallel's safe_fetch already has one, for the identical
        reason) - see SESSION.md.
        """
        try:
            fetcher = get_fetcher(app_config, source=source, force_mock=False)
            posts = self._fetch(fetcher, query, errors)
            logger.info("%s: fetched %d discussion(s)", source, len(posts))
            return posts
        except Exception as exc:  # noqa: BLE001 — per-source isolation is the entire point here, see docstring
            logger.warning("%s fetch failed: %s", source, exc)
            errors.append(f"{source} fetch failed: {type(exc).__name__}: {exc}")
            return []

    def _fetch_all_sources(
        self, app_config: Config, sources: List[str], query: FetchQuery, errors: List[str]
    ) -> List[FetchedPost]:
        """Fetches from multiple sources simultaneously via a thread
        pool (I/O-bound HTTP calls, same "threads not processes"
        reasoning as BaseFetcher.fetch_parallel) and merges the results
        with the existing _merge_posts() dedup helper (by
        FetchedPost.id - a genuine cross-source duplicate is
        effectively impossible between GitHub and Hacker News, but kept
        for consistency/defense in depth, and it's exactly what a
        second oversample round already relies on for the single-source
        case).

        Each source's own FetchQuery.limit is query.limit split evenly
        across `sources` (_split_limit) - the combined result still
        targets roughly query.limit discussions overall, not
        query.limit from every source independently.
        """
        logger.info("Fetching from %d source(s) simultaneously: %s", len(sources), sources)
        per_source_limit = self._split_limit(query.limit, len(sources))
        per_source_query = replace(query, limit=per_source_limit)

        with ThreadPoolExecutor(max_workers=len(sources)) as executor:
            futures = {
                executor.submit(self._fetch_from_source, source, app_config, per_source_query, errors): source
                for source in sources
            }

            all_posts: List[FetchedPost] = []
            for future in futures:
                source = futures[future]
                results = future.result()  # _fetch_from_source never raises - see its own docstring
                all_posts = _merge_posts(all_posts, results)
                logger.info("%s: %d discussion(s) added (%d total after dedup)", source, len(results), len(all_posts))

        logger.info("Total combined: %d discussion(s)", len(all_posts))
        return all_posts

    def _should_oversample(self, clusters: List[OpportunityCluster], fetched_limit: int) -> bool:
        """True only for a GitHub/Hacker News run with num_reports set,
        that came up short of that many clusters, and still has headroom
        under post_limit left to fetch more with. If fetched_limit
        already equals post_limit, every available fetch has already
        happened - coming up short at that point means genuinely fewer
        than num_reports discussions exist, which is the documented,
        expected "return fewer than requested" outcome, not a bug to
        retry around.
        """
        if self._config.source not in _KEYWORD_DRIVEN_SOURCES or not self._config.num_reports:
            return False
        return len(clusters) < self._config.num_reports and fetched_limit < self._config.post_limit

    def _oversample_for_report_count(
        self,
        fetcher: Fetcher,
        community: str,
        search_keyword: Optional[str],
        expanded_terms: Optional[List[str]],
        posts: List[FetchedPost],
        clusters_so_far: int,
        active_provider: AIProvider,
        errors: List[str],
    ) -> Tuple[List[FetchedPost], List[DiscussionInsight], List[OpportunityCluster]]:
        """One additional fetch round (this method has exactly one call
        site in run(), never a loop - see _OVERSAMPLE_MULTIPLIER's
        comment), requesting up to post_limit discussions total, merged
        with what was already fetched and re-analyzed from scratch over
        the merged set - simpler than incrementally extending
        insights/clusters, and no more costly in practice since
        CachingAIProvider (when enabled) makes re-extracting an
        already-seen post a cache hit rather than a real API call.

        search_keyword/expanded_terms are the already-expanded GitHub
        search term(s) (see run()'s own QueryExpander.expand() call) -
        reused as-is rather than re-expanded, so this round searches
        for the exact same thing(s) round 1 did, just with a bigger
        limit.
        """
        logger.info(
            "Only %d/%d requested report(s) found from %d discussion(s); fetching more (up to the "
            "%d-discussion limit) before giving up.",
            clusters_so_far,
            self._config.num_reports,
            len(posts),
            self._config.post_limit,
        )
        query = FetchQuery(
            community=community, keyword=search_keyword, keywords=expanded_terms, limit=self._config.post_limit
        )
        more_posts = self._fetch(fetcher, query, errors)
        merged_posts = _merge_posts(posts, more_posts)
        insights = self._analyze(merged_posts, active_provider, errors)
        clusters = self._cluster(insights, active_provider, errors)
        if len(clusters) < self._config.num_reports:
            logger.info(
                "Still only %d/%d requested report(s) after oversampling - only %d distinct discussion(s) "
                "were available for search terms %r.",
                len(clusters),
                self._config.num_reports,
                len(merged_posts),
                search_keyword,
            )
        return merged_posts, insights, clusters

    def _oversample_for_report_count_multi(
        self,
        app_config: Config,
        active_sources: List[str],
        community: str,
        search_keyword: Optional[str],
        expanded_terms: Optional[List[str]],
        posts: List[FetchedPost],
        clusters_so_far: int,
        active_provider: AIProvider,
        errors: List[str],
    ) -> Tuple[List[FetchedPost], List[DiscussionInsight], List[OpportunityCluster]]:
        """The source="all" equivalent of _oversample_for_report_count()
        - same one-more-round, re-analyze-from-scratch-over-the-merged-
        set shape (see that method's own docstring); a separate method
        rather than a shared one because there's no single `fetcher` to
        reuse here - every active source is fetched again via
        _fetch_all_sources(), each getting its own even split of
        post_limit (see _split_limit), exactly like the initial fetch.
        """
        logger.info(
            "Only %d/%d requested report(s) found from %d discussion(s); fetching more from %s (up to the "
            "%d-discussion limit) before giving up.",
            clusters_so_far,
            self._config.num_reports,
            len(posts),
            active_sources,
            self._config.post_limit,
        )
        query = FetchQuery(
            community=community, keyword=search_keyword, keywords=expanded_terms, limit=self._config.post_limit
        )
        more_posts = self._fetch_all_sources(app_config, active_sources, query, errors)
        merged_posts = _merge_posts(posts, more_posts)
        insights = self._analyze(merged_posts, active_provider, errors)
        clusters = self._cluster(insights, active_provider, errors)
        if len(clusters) < self._config.num_reports:
            logger.info(
                "Still only %d/%d requested report(s) after oversampling - only %d distinct discussion(s) "
                "were available for search terms %r across %s.",
                len(clusters),
                self._config.num_reports,
                len(merged_posts),
                search_keyword,
                active_sources,
            )
        return merged_posts, insights, clusters

    def _fetch(self, fetcher: Fetcher, query: FetchQuery, errors: List[str]) -> List[FetchedPost]:
        logger.info("Fetching (community=%s, keyword=%s, limit=%d)...", query.community, query.keyword, query.limit)
        try:
            posts = _fetch_with_retry(fetcher, query)
        except FetcherError as exc:
            errors.append(f"Fetch failed after {_FETCH_MAX_ATTEMPTS} attempts: {exc}")
            logger.error("Fetch failed after retries: %s", exc)
            return []
        logger.info("Fetched %d post(s).", len(posts))
        return posts

    def _analyze(
        self,
        posts: List[FetchedPost],
        ai_provider: AIProvider,
        errors: List[str],
        on_progress: Optional[ProgressCallback] = None,
    ) -> List[DiscussionInsight]:
        """Extracts every post in parallel batches - see
        Extractor.extract_all_parallel(). Progress is reported per
        batch, not per post: real parallel completion order can't
        preserve the old sequential loop's guarantee that percent only
        ever increases (see extract_all_parallel's own docstring) -
        per-batch events stay monotonic (always emitted from this
        thread, after a whole batch finishes, in batch order) without
        that risk, at the cost of coarser granularity during this stage.
        """
        if not posts:
            return []
        extractor = Extractor(ai_provider)
        total = len(posts)

        def on_error(post: FetchedPost, exc: Exception) -> None:
            # Extractor._extract_single_safe already logs a warning for
            # this internally - only the errors list (surfaced to the
            # user, e.g. the dashboard's "Show details" disclosure)
            # needs the specific message recorded here too.
            errors.append(f"Extraction failed for {post.url}: {exc}")

        def on_batch_complete(done: int, total_count: int) -> None:
            self._emit(
                on_progress, "analyze", f"🤖 Analyzed {done}/{total_count} discussions...", 40 + round(25 * done / total_count)
            )

        insights = extractor.extract_all_parallel(posts, on_error=on_error, on_batch_complete=on_batch_complete)
        logger.info("Analyzed %d of %d post(s).", len(insights), len(posts))
        return insights

    def _cluster(
        self,
        insights: List[DiscussionInsight],
        ai_provider: AIProvider,
        errors: List[str],
        on_progress: Optional[ProgressCallback] = None,
    ) -> List[OpportunityCluster]:
        if not insights:
            return []
        self._emit(on_progress, "cluster", f"🔗 Clustering {len(insights)} insights...", 70)
        aggregator = Aggregator(ai_provider)
        clusters = aggregator.aggregate(insights)
        if aggregator.last_method == "lexical_fallback":
            message = (
                f"AI-assisted clustering unavailable ({aggregator.last_fallback_reason}); "
                f"used keyword-overlap fallback, which under-merges real duplicates."
            )
            errors.append(message)
            logger.warning(message)
        self._emit(on_progress, "cluster", f"📊 Found {len(clusters)} opportunity clusters", 80)
        logger.info("Grouped into %d cluster(s) via %s.", len(clusters), aggregator.last_method)
        return clusters

    def _verify(
        self,
        insights: List[DiscussionInsight],
        posts: List[FetchedPost],
        on_progress: Optional[ProgressCallback] = None,
    ) -> VerificationReport:
        if not insights:
            return VerificationReport(
                total_claims=0, verified_count=0, partial_count=0, unverified_count=0, verification_rate=0.0, results=[]
            )
        self._emit(on_progress, "verify", "✔️ Verifying evidence and quotes...", 85)
        report = Verifier().verify_all(insights, posts)
        self._emit(on_progress, "verify", f"✔️ Verification complete — {report.verified_count} verified", 90)
        logger.info(
            "Verified %d claim(s): %.1f%% verified, %d partial, %d unverified.",
            report.total_claims,
            report.verification_rate * 100,
            report.partial_count,
            report.unverified_count,
        )
        return report

    def _save_outputs(self, report: InsightReport, start_time: datetime) -> Optional[Path]:
        if self._config.report_format not in ("markdown", "both"):
            return None
        path = self._config.output_dir / f"report_{start_time:%Y%m%d_%H%M%S}.md"
        save_markdown_file(report, path)
        logger.info("Markdown report saved to %s", path)
        return path

    def _save_summary(self, summary: PipelineExecutionSummary, start_time: datetime) -> None:
        path = self._config.output_dir / f"pipeline_run_{start_time:%Y%m%d_%H%M%S}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_summary_to_dict(summary), indent=2), encoding="utf-8")


def _resolve_ai_provider_and_label(config: PipelineConfig, app_config: Config) -> tuple:
    force_mock = config.ai_provider == "mock"
    provider = get_ai_provider(app_config, force_mock=force_mock)
    if force_mock or not app_config.gemini_configured:
        label = "Mock AI provider"
    else:
        label = f"Google Gemini ({app_config.gemini_model})"
    return provider, label


def _merge_posts(existing: List[FetchedPost], new: List[FetchedPost]) -> List[FetchedPost]:
    """Combines an oversampling round's results with what was already
    fetched, de-duplicated by FetchedPost.id and order-preserving.
    GitHubFetcher's search re-fetches from page 1 each round (see its
    own docstring on Search API relevance ordering), so `new` is
    expected to mostly overlap `existing` plus some genuinely new
    issues past the first fetch's smaller page size - this is what
    turns that overlap into a clean, single deduplicated list.
    """
    seen = {post.id for post in existing}
    merged = list(existing)
    for post in new:
        if post.id not in seen:
            seen.add(post.id)
            merged.append(post)
    return merged


def _fetch_with_retry(fetcher: Fetcher, query: FetchQuery) -> List[FetchedPost]:
    last_exc: Optional[FetcherError] = None
    for attempt in range(_FETCH_MAX_ATTEMPTS):
        try:
            return fetcher.fetch(query)
        except FetcherError as exc:
            last_exc = exc
            logger.warning("Fetch attempt %d/%d failed: %s", attempt + 1, _FETCH_MAX_ATTEMPTS, exc)
            if attempt < _FETCH_MAX_ATTEMPTS - 1:
                time.sleep(_FETCH_BASE_DELAY_SECONDS * (2**attempt))
    assert last_exc is not None
    raise last_exc


def _summary_to_dict(summary: PipelineExecutionSummary) -> dict:
    return {
        "start_time": summary.start_time.isoformat(),
        "end_time": summary.end_time.isoformat(),
        "duration_seconds": summary.duration_seconds,
        "posts_fetched": summary.posts_fetched,
        "posts_analyzed": summary.posts_analyzed,
        "ai_calls_made": summary.ai_calls_made,
        "cache_hits": summary.cache_hits,
        "cache_misses": summary.cache_misses,
        "clusters_found": summary.clusters_found,
        "errors": summary.errors,
        "report_path": str(summary.report_path) if summary.report_path else None,
        "succeeded": summary.succeeded,
    }
