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
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from src.ai import get_ai_provider
from src.ai.base import AIProvider
from src.config import Config, load_config
from src.fetchers import FetcherError, get_fetcher
from src.fetchers.base import Fetcher
from src.insights.aggregator import Aggregator
from src.insights.extractor import Extractor, InsightExtractionError
from src.insights.models import DiscussionInsight, OpportunityCluster
from src.models import FetchedPost, FetchQuery
from src.pipeline.cache import CachingAIProvider, ResponseCache
from src.reporting.formatter import save_markdown_file
from src.reporting.models import InsightReport
from src.reporting.report_generator import generate_report
from src.verification.models import VerificationReport
from src.verification.verifier import Verifier

logger = logging.getLogger(__name__)

_FETCH_MAX_ATTEMPTS = 3
_FETCH_BASE_DELAY_SECONDS = 1.0


@dataclass(frozen=True)
class PipelineConfig:
    """Every configuration option requirement 3 named.

    Attributes:
        subreddit: Passed through as FetchQuery.community when
            source="reddit" (the default). Ignored by the mock fetcher,
            but still required by argparse/AnalyzeRequest for clarity
            about what a real run would target.
        source: Which Fetcher to use - "reddit" (default) or "github".
            Passed straight through to get_fetcher()'s own source
            parameter (src/fetchers/__init__.py), which already
            supported this before any caller actually passed it.
        keyword: Optional keyword filter for Reddit, passed through
            unchanged. Required (not optional) when source="github":
            GitHubFetcher no longer takes an explicit repo - it uses
            this same keyword to discover candidate repos via GitHub's
            Search API, then applies it again as the usual post-fetch
            filter. AnalyzeRequest enforces the "required for github"
            rule at the API layer; the CLI has no --source flag yet
            (see ENGINEERING_GUIDE.md's known limitations).
        post_limit: Max posts to fetch.
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
    """

    def __init__(self, wrapped: AIProvider) -> None:
        self._wrapped = wrapped
        self.call_count = 0

    def check_connection(self) -> None:
        self._wrapped.check_connection()

    def generate_text(self, prompt: str) -> str:
        self.call_count += 1
        return self._wrapped.generate_text(prompt)


class Pipeline:
    """Runs the full Fetch -> Analyze -> Cluster -> Verify -> Report
    sequence for one PipelineConfig.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._config = config

    def run(self) -> PipelineRunResult:
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
            fetcher = get_fetcher(
                app_config, source=self._config.source, force_mock=self._config.force_mock_fetch
            )
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

            # GitHubFetcher ignores FetchQuery.community entirely (repo
            # discovery is keyword-driven - see github_fetcher.py); the
            # keyword is passed here too only so log lines naming
            # "community" print something meaningful for a GitHub run.
            community = self._config.keyword or "" if self._config.source == "github" else self._config.subreddit
            query = FetchQuery(community=community, keyword=self._config.keyword, limit=self._config.post_limit)

            posts = self._fetch(fetcher, query, errors)
            insights = self._analyze(posts, active_provider, errors)
            clusters = self._cluster(insights, active_provider, errors)

            verification_report = self._verify(insights, posts)
            ai_calls_made = counting_provider.call_count
            if caching_provider is not None:
                cache_hits = caching_provider.hits
                cache_misses = caching_provider.misses

            insight_report = generate_report(clusters, verification_report, posts, ai_provider_label)
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
            clusters_found=len(clusters),
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
        return PipelineRunResult(summary=summary, report=insight_report)

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
        self, posts: List[FetchedPost], ai_provider: AIProvider, errors: List[str]
    ) -> List[DiscussionInsight]:
        if not posts:
            return []
        extractor = Extractor(ai_provider)
        insights: List[DiscussionInsight] = []
        for post in posts:
            try:
                insights.append(extractor.extract(post))
            except InsightExtractionError as exc:
                message = f"Extraction failed for {post.url}: {exc}"
                errors.append(message)
                logger.warning(message)
        logger.info("Analyzed %d of %d post(s).", len(insights), len(posts))
        return insights

    def _cluster(
        self, insights: List[DiscussionInsight], ai_provider: AIProvider, errors: List[str]
    ) -> List[OpportunityCluster]:
        if not insights:
            return []
        aggregator = Aggregator(ai_provider)
        clusters = aggregator.aggregate(insights)
        if aggregator.last_method == "lexical_fallback":
            message = (
                f"AI-assisted clustering unavailable ({aggregator.last_fallback_reason}); "
                f"used keyword-overlap fallback, which under-merges real duplicates."
            )
            errors.append(message)
            logger.warning(message)
        logger.info("Grouped into %d cluster(s) via %s.", len(clusters), aggregator.last_method)
        return clusters

    def _verify(self, insights: List[DiscussionInsight], posts: List[FetchedPost]) -> VerificationReport:
        if not insights:
            return VerificationReport(
                total_claims=0, verified_count=0, partial_count=0, unverified_count=0, verification_rate=0.0, results=[]
            )
        report = Verifier().verify_all(insights, posts)
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
