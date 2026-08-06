"""Tests for src/pipeline/.

Every Pipeline constructed here explicitly sets ai_provider="mock" (and
usually force_mock_fetch=True too) — the real .env in this project has
a real GEMINI_API_KEY configured, and ai_provider="auto" would silently
make real, billed API calls during what's supposed to be a fast,
offline test suite. This is deliberate test hygiene, not incidental.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import pytest

from src.ai import get_ai_provider
from src.ai.base import AIProvider
from src.ai.gemini_provider import GeminiProvider
from src.ai.mock_provider import MockAIProvider
from src.config import Config
from src.fetchers import get_fetcher
from src.fetchers.base import Fetcher, FetcherError
from src.fetchers.mock_fetcher import MockFetcher
from src.fetchers.reddit_fetcher import RedditFetcher
from src.models import FetchedPost, FetchQuery
from src.pipeline.pipeline import (
    Pipeline,
    PipelineConfig,
    _CountingAIProvider,
    _fetch_with_retry,
    calculate_fetch_limit,
)


def make_config(reddit_configured: bool = False, gemini_configured: bool = False) -> Config:
    return Config(
        gemini_api_key=("fake-key" if gemini_configured else None),
        gemini_model="gemini-flash-latest",
        reddit_client_id=("fake-id" if reddit_configured else None),
        reddit_client_secret=("fake-secret" if reddit_configured else None),
        reddit_user_agent="test-agent",
    )


# --- force_mock overrides on the factories ---------------------------------


def test_force_mock_fetch_overrides_real_reddit_config():
    config = make_config(reddit_configured=True)
    assert config.reddit_configured is True  # sanity: would normally pick RedditFetcher

    fetcher = get_fetcher(config, force_mock=True)
    assert isinstance(fetcher, MockFetcher)
    assert not isinstance(fetcher, RedditFetcher)


def test_without_force_mock_real_reddit_config_still_used():
    config = make_config(reddit_configured=True)
    fetcher = get_fetcher(config, force_mock=False)
    assert isinstance(fetcher, RedditFetcher)


def test_force_mock_ai_overrides_real_gemini_config():
    config = make_config(gemini_configured=True)
    provider = get_ai_provider(config, force_mock=True)
    assert isinstance(provider, MockAIProvider)
    assert not isinstance(provider, GeminiProvider)


# --- GitHubFetcher end-to-end wiring (source/keyword) ---------------------------


def test_pipeline_passes_source_to_get_fetcher_and_keyword_as_fetch_query_community(tmp_path: Path, monkeypatch):
    """The real, previously-missing wiring: source="github" must reach
    get_fetcher()'s own source parameter (not just sit unused on
    PipelineConfig). GitHubFetcher discovers repos from keyword alone
    now (no repo field exists anymore - see github_fetcher.py), so
    keyword - not subreddit - becomes FetchQuery.community for a GitHub
    run too (community itself is otherwise unused by GitHubFetcher;
    this just confirms subreddit is never leaked through instead).
    Stubs get_fetcher itself (not just Fetcher) so this proves the call
    arguments Pipeline.run() actually passes, independent of any
    API-layer stubbing.
    """
    import src.pipeline.pipeline as pipeline_module

    captured: dict = {}

    class _StubFetcher(Fetcher):
        def fetch(self, query: FetchQuery) -> List[FetchedPost]:
            captured["community"] = query.community
            return []

    def _stub_get_fetcher(config, *, source="reddit", force_mock=False):
        captured["source"] = source
        captured["force_mock"] = force_mock
        return _StubFetcher()

    monkeypatch.setattr(pipeline_module, "get_fetcher", _stub_get_fetcher)

    config = PipelineConfig(
        source="github",
        keyword="invoicing",
        subreddit="should-be-ignored",
        post_limit=1,
        output_dir=tmp_path,
        ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    Pipeline(config).run()

    assert captured["source"] == "github"
    assert captured["force_mock"] is False
    assert captured["community"] == "invoicing"


def test_pipeline_defaults_to_reddit_source_and_subreddit_as_community(tmp_path: Path, monkeypatch):
    import src.pipeline.pipeline as pipeline_module

    captured: dict = {}

    class _StubFetcher(Fetcher):
        def fetch(self, query: FetchQuery) -> List[FetchedPost]:
            captured["community"] = query.community
            return []

    def _stub_get_fetcher(config, *, source="reddit", force_mock=False):
        captured["source"] = source
        return _StubFetcher()

    monkeypatch.setattr(pipeline_module, "get_fetcher", _stub_get_fetcher)

    config = PipelineConfig(
        subreddit="startups", post_limit=1, output_dir=tmp_path, ai_provider="mock", cache_path=tmp_path / "ai_cache.json"
    )
    Pipeline(config).run()

    assert captured["source"] == "reddit"
    assert captured["community"] == "startups"


# --- GitHub natural-language keyword extraction (src/insights/keyword_extraction.py) --


class _StubQueryExpander:
    """Stands in for src.search.query_expander.QueryExpander in tests
    that only care about how Pipeline.run() wires it in, not its own
    expansion logic (that's tests/search/test_query_expander.py's job).
    Records every expand() call on the class itself, since Pipeline
    constructs a fresh instance inline rather than reusing one.
    """

    calls: List[str] = []
    return_value: List[str] = ["invoicing saas", "billing tool"]

    def __init__(self, ai_provider) -> None:
        self.ai_provider = ai_provider

    def expand(self, user_input: str) -> List[str]:
        type(self).calls.append(user_input)
        return type(self).return_value


def test_pipeline_expands_query_before_github_fetch(tmp_path: Path, monkeypatch):
    """QueryExpander replaced extract_search_terms as the mechanism
    that derives GitHub's search keyword (see PipelineConfig.keyword's
    and src/search/query_expander.py's docstrings for why) - this
    proves the real equivalent: expand() runs before the fetch, and
    only the first of its returned terms - not the raw natural-language
    input - is what the fetcher actually receives.
    """
    import src.pipeline.pipeline as pipeline_module

    captured: dict = {}
    _StubQueryExpander.calls = []
    _StubQueryExpander.return_value = ["invoicing automation", "billing saas tool"]

    class _StubFetcher(Fetcher):
        def fetch(self, query: FetchQuery) -> List[FetchedPost]:
            captured["fetch_keyword"] = query.keyword
            return []

    monkeypatch.setattr(pipeline_module, "QueryExpander", _StubQueryExpander)
    monkeypatch.setattr(
        pipeline_module, "get_fetcher", lambda config, *, source="reddit", force_mock=False: _StubFetcher()
    )

    config = PipelineConfig(
        source="github",
        keyword="problems with invoice automation",
        post_limit=5,
        output_dir=tmp_path,
        ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    Pipeline(config).run()

    assert _StubQueryExpander.calls == ["problems with invoice automation"]
    assert captured["fetch_keyword"] == "invoicing automation"  # first expanded term, not the raw input


def test_pipeline_does_not_expand_query_for_reddit_source(tmp_path: Path, monkeypatch):
    """QueryExpander is GitHub-only (see PipelineConfig.keyword's
    docstring) - a Reddit run's keyword must reach the fetcher
    completely unchanged, with no AI call in between.
    """
    import src.pipeline.pipeline as pipeline_module

    captured: dict = {}
    _StubQueryExpander.calls = []
    _StubQueryExpander.return_value = ["should never be used"]

    class _StubFetcher(Fetcher):
        def fetch(self, query: FetchQuery) -> List[FetchedPost]:
            captured["fetch_keyword"] = query.keyword
            return []

    monkeypatch.setattr(pipeline_module, "QueryExpander", _StubQueryExpander)
    monkeypatch.setattr(
        pipeline_module, "get_fetcher", lambda config, *, source="reddit", force_mock=False: _StubFetcher()
    )

    config = PipelineConfig(
        source="reddit",
        subreddit="startups",
        keyword="invoice automation problems",
        post_limit=5,
        output_dir=tmp_path,
        ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    Pipeline(config).run()

    assert _StubQueryExpander.calls == []
    assert captured["fetch_keyword"] == "invoice automation problems"


# --- Adaptive fetch-limit calculation (calculate_fetch_limit) -----------------------


def test_calculate_fetch_limit_small():
    assert calculate_fetch_limit(5) == 15
    assert calculate_fetch_limit(10) == 30


def test_calculate_fetch_limit_medium():
    assert calculate_fetch_limit(11) == 22
    assert calculate_fetch_limit(30) == 60


def test_calculate_fetch_limit_large():
    assert calculate_fetch_limit(31) == 46
    assert calculate_fetch_limit(50) == 75


def test_calculate_fetch_limit_xlarge():
    assert calculate_fetch_limit(51) == 63
    assert calculate_fetch_limit(100) == 125


def test_calculate_fetch_limit_hardcap():
    assert calculate_fetch_limit(101) == 111
    assert calculate_fetch_limit(500) == 200
    assert calculate_fetch_limit(1000) == 200


def test_calculate_fetch_limit_rejects_non_positive():
    with pytest.raises(ValueError):
        calculate_fetch_limit(0)


class _PartialExtractionAIProvider(AIProvider):
    """Models "N discussions fetched, only M pass quality filtering"
    deterministically: the first `passing` extraction calls get real,
    quote-verified MockAIProvider output; every extraction call after
    that gets a syntactically-valid response whose evidence_quote is
    NOT a substring of the source text, which Extractor's own
    verified-quote guardrail rejects (InsightExtractionError) - the
    same real rejection path a genuinely low-quality AI response would
    hit, not a shortcut around it. Clustering always makes one
    singleton cluster per surviving insight, same as MockAIProvider's
    own clustering response.
    """

    def __init__(self, passing: int) -> None:
        self._passing = passing
        self._extraction_calls = 0
        self._mock = MockAIProvider()

    def check_connection(self) -> None:
        return

    def generate_text(self, prompt: str) -> str:
        if 'Discussion text:\n"""' in prompt:
            self._extraction_calls += 1
            if self._extraction_calls <= self._passing:
                return self._mock.generate_text(prompt)
            return json.dumps(
                {
                    "primary_pain_point": {
                        "description": "unverifiable",
                        "evidence_quote": "this exact sentence is not present anywhere in the source text",
                    },
                    "secondary_pain_points": [],
                    "user_persona": "unverifiable",
                    "feature_requests": [],
                    "buying_signals": [],
                    "emotional_sentiment": "Neutral",
                    "urgency_score": 1,
                    "opportunity_score": 1,
                    "confidence": "Weak",
                    "startup_opportunity": "unverifiable",
                    "supporting_evidence": [],
                }
            )
        return self._mock.generate_text(prompt)  # clustering: MockAIProvider's own singleton-per-index behavior


def test_pipeline_uses_calculated_limit(tmp_path: Path, monkeypatch):
    fetcher = _AvailablePostsFetcher(available=20)
    _patch_github_fetch_and_clustering(monkeypatch, fetcher, MockAIProvider())

    config = PipelineConfig(
        source="github",
        keyword="invoicing",
        post_limit=50,
        num_reports=5,
        output_dir=tmp_path,
        ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    Pipeline(config).run()

    assert fetcher.calls[0] == 15  # calculate_fetch_limit(5)


def test_pipeline_trims_to_requested(tmp_path: Path, monkeypatch):
    """15 discussions fetched, 8 pass extraction/quality filtering,
    user requested 5 - more than enough survived, so the deliverable
    is trimmed to exactly 5.
    """
    fetcher = _AvailablePostsFetcher(available=15)
    _patch_github_fetch_and_clustering(monkeypatch, fetcher, _PartialExtractionAIProvider(passing=8))

    config = PipelineConfig(
        source="github",
        keyword="invoicing",
        post_limit=50,
        num_reports=5,
        output_dir=tmp_path,
        ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    result = Pipeline(config).run()

    assert fetcher.calls == [15]  # 8 >= 5 requested, so no oversample round needed
    assert len(result.report.top_opportunities) == 5


def test_pipeline_handles_fewer_than_requested(tmp_path: Path, monkeypatch):
    """15 discussions fetched, only 3 pass extraction/quality
    filtering, user requested 5 - fewer survived than requested; the
    pipeline must still succeed (not crash/raise) and honestly return
    the 3 that are genuinely available, never fabricating 2 more.
    """
    fetcher = _AvailablePostsFetcher(available=15)
    _patch_github_fetch_and_clustering(monkeypatch, fetcher, _PartialExtractionAIProvider(passing=3))

    config = PipelineConfig(
        source="github",
        keyword="invoicing",
        post_limit=50,
        num_reports=5,
        output_dir=tmp_path,
        ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    result = Pipeline(config).run()  # must not raise

    assert result.summary.succeeded is True
    assert len(result.report.top_opportunities) == 3


def test_pipeline_large_request_warning(tmp_path: Path, monkeypatch, caplog):
    """The task's own edge-case spec ties the "large request" warning
    to `requested > 200` (calculate_fetch_limit's absolute hard cap),
    not to a specific example value - verified with 250 here, since
    150 (the task's own "Test C" example) does not actually exceed 200
    and therefore does not trigger this path under the given formula;
    see this task's completion report for that discrepancy.
    """
    fetcher = _AvailablePostsFetcher(available=300)
    _patch_github_fetch_and_clustering(monkeypatch, fetcher, MockAIProvider())

    config = PipelineConfig(
        source="github",
        keyword="developer tools",
        post_limit=300,
        num_reports=250,
        output_dir=tmp_path,
        ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    with caplog.at_level("WARNING", logger="src.pipeline.pipeline"):
        Pipeline(config).run()

    assert fetcher.calls[0] == 200  # calculate_fetch_limit's absolute hard cap
    assert any("Large request" in record.message for record in caplog.records)


def test_pipeline_stats_show_fetch_limit(tmp_path: Path, monkeypatch):
    fetcher = _AvailablePostsFetcher(available=20)
    _patch_github_fetch_and_clustering(monkeypatch, fetcher, MockAIProvider())

    config = PipelineConfig(
        source="github",
        keyword="invoicing",
        post_limit=50,
        num_reports=5,
        output_dir=tmp_path,
        ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    result = Pipeline(config).run()

    assert result.summary.posts_fetched == 15  # calculate_fetch_limit(5)
    assert result.summary.clusters_found == 5  # delivered/capped count


# --- GitHub report-count reliability (PipelineConfig.num_reports) -------------------


def _post(index: int) -> FetchedPost:
    return FetchedPost(
        source="github",
        item_type="post",
        id=f"post-{index}",
        title=f"issue {index}",
        text=f"pain point number {index} described here in enough detail to extract.",
        author="someone",
        url=f"https://github.com/example/repo/issues/{index}",
        created_at=datetime.now(timezone.utc),
        score=0,
        is_mock=False,
    )


class _AvailablePostsFetcher(Fetcher):
    """Simulates a real source with a fixed total pool of `available`
    distinct discussions - fetch() never returns more than that,
    regardless of how large a limit is requested (the same way a real
    GitHub search can only ever return as many genuinely matching
    issues as exist). Records every requested limit so tests can assert
    on the pipeline's actual fetch pattern (one call vs. an oversample
    round).
    """

    def __init__(self, available: int) -> None:
        self._available = available
        self.calls: List[int] = []

    def fetch(self, query: FetchQuery) -> List[FetchedPost]:
        self.calls.append(query.limit)
        return [_post(i) for i in range(min(query.limit, self._available))]


class _MergeEveryFourAIProvider(AIProvider):
    """Test double standing in for a real AI provider's clustering
    judgment: extraction reuses MockAIProvider's real (schema-valid,
    quote-verified) behavior unchanged, but clustering merges every 4
    consecutive discussions into one cluster (ceil(n/4) clusters for n
    discussions) instead of MockAIProvider's always-1-cluster-per-post
    default.

    This is what makes num_reports's oversampling round meaningful to
    test at all: with MockAIProvider's real singleton-per-post
    behavior, requesting 3x num_reports discussions up front always
    already yields >= num_reports clusters whenever that many
    discussions exist, so the "still short after round 1, try once
    more" path never actually triggers. A real provider that finds
    duplicates (the entire reason clustering exists - see
    src/insights/aggregator.py's module docstring) can plausibly merge
    a first, smaller batch down below the requested count while a
    larger batch - reachable only via a second fetch round - has
    genuinely more distinct underlying pain points to surface.
    """

    def __init__(self) -> None:
        self._mock = MockAIProvider()

    def check_connection(self) -> None:
        return

    def generate_text(self, prompt: str) -> str:
        if 'Discussion text:\n"""' in prompt:
            return self._mock.generate_text(prompt)  # extraction: unchanged real mock behavior
        indices = [int(i) for i in re.findall(r"^\[(\d+)\]", prompt, re.MULTILINE)]
        clusters = [indices[i : i + 4] for i in range(0, len(indices), 4)]
        return json.dumps(
            {"clusters": [{"label": f"cluster {i}", "member_indices": members} for i, members in enumerate(clusters)]}
        )


def _patch_github_fetch_and_clustering(monkeypatch, fetcher: Fetcher, ai_provider: AIProvider) -> None:
    import src.pipeline.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "get_fetcher", lambda config, *, source="reddit", force_mock=False: fetcher)
    monkeypatch.setattr(pipeline_module, "get_ai_provider", lambda config, *, force_mock=False: ai_provider)


def test_num_reports_initial_fetch_requests_oversample_multiplier(tmp_path: Path, monkeypatch):
    fetcher = _AvailablePostsFetcher(available=20)
    _patch_github_fetch_and_clustering(monkeypatch, fetcher, MockAIProvider())

    config = PipelineConfig(
        source="github",
        keyword="invoicing",
        post_limit=25,
        num_reports=3,
        output_dir=tmp_path,
        ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    result = Pipeline(config).run()

    assert fetcher.calls == [9]  # 3x num_reports, not post_limit
    assert result.summary.succeeded is True
    # clusters_found reflects the delivered/capped count (3), not the
    # full 9 found - see run()'s summary construction comment: this
    # differs from posts_fetched/posts_analyzed, which do report the
    # full analysis breadth; InsightReport.project_health still does too.
    assert result.summary.clusters_found == 3
    assert len(result.report.top_opportunities) == 3  # surfaced deliverable capped to what was requested


def test_num_reports_returns_requested_count_when_data_is_sufficient(tmp_path: Path, monkeypatch):
    """Core reliability guarantee: given enough real underlying data
    (even after a first batch merges down below the requested count),
    a second, larger fetch round finds enough genuinely distinct
    opportunities to satisfy the request exactly.
    """
    fetcher = _AvailablePostsFetcher(available=40)
    _patch_github_fetch_and_clustering(monkeypatch, fetcher, _MergeEveryFourAIProvider())

    config = PipelineConfig(
        source="github",
        keyword="invoicing",
        post_limit=50,
        num_reports=5,
        output_dir=tmp_path,
        ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    result = Pipeline(config).run()

    assert fetcher.calls == [15, 50]  # round 1 (3x5, short after merging) + one oversample round at post_limit
    assert result.summary.succeeded is True
    assert result.summary.posts_fetched == 40  # merged/deduplicated across both rounds, not 15+40
    assert result.summary.clusters_found == 5  # delivered/capped count, not the full ceil(40/4)=10 found
    assert len(result.report.top_opportunities) == 5  # exactly what was requested


def test_num_reports_returns_fewer_when_genuinely_insufficient_data(tmp_path: Path, monkeypatch):
    """'Only return fewer than N if genuinely fewer are available':
    with just 8 real discussions total, no amount of oversampling can
    produce 5 distinct clusters under a 4-per-cluster merge ratio - the
    pipeline must try the one extra round, then honestly stop rather
    than loop indefinitely or fabricate additional reports.
    """
    fetcher = _AvailablePostsFetcher(available=8)
    _patch_github_fetch_and_clustering(monkeypatch, fetcher, _MergeEveryFourAIProvider())

    config = PipelineConfig(
        source="github",
        keyword="invoicing",
        post_limit=50,
        num_reports=5,
        output_dir=tmp_path,
        ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    result = Pipeline(config).run()

    assert fetcher.calls == [15, 50]  # exactly one oversample round, never an unbounded retry loop
    assert result.summary.succeeded is True  # a genuine shortfall is not a pipeline failure
    assert result.summary.posts_fetched == 8
    assert result.summary.clusters_found == 2  # ceil(8/4)
    assert len(result.report.top_opportunities) == 2  # honestly fewer than the 5 requested, never fabricated


def test_num_reports_ignored_for_non_github_source(tmp_path: Path, monkeypatch):
    """num_reports is documented as GitHub-only (Reddit's fetch
    mechanism doesn't support the same oversample-and-retry approach) -
    a Reddit run must behave exactly as if num_reports were never set:
    a single fetch at post_limit, no oversampling, no capping of
    top_opportunities.
    """
    fetcher = _AvailablePostsFetcher(available=2)
    _patch_github_fetch_and_clustering(monkeypatch, fetcher, MockAIProvider())

    config = PipelineConfig(
        source="reddit",
        subreddit="test",
        post_limit=10,
        num_reports=5,
        output_dir=tmp_path,
        ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    result = Pipeline(config).run()

    assert fetcher.calls == [10]  # post_limit directly, never 3x num_reports
    assert result.summary.clusters_found == 2
    assert len(result.report.top_opportunities) == 2  # not capped/truncated to num_reports


# --- Multi-source fetching (source="all") -------------------------------------


def _make_fetcher(posts: List[FetchedPost], *, delay: float = 0.0, calls: list | None = None) -> Fetcher:
    """A minimal Fetcher stub returning a fixed list of posts, optionally
    recording the FetchQuery it was called with (for limit/dedup
    assertions) and/or sleeping first (for the parallelism timing test).
    """

    class _StubFetcher(Fetcher):
        def fetch(self, query: FetchQuery) -> List[FetchedPost]:
            if calls is not None:
                calls.append(query.limit)
            if delay:
                time.sleep(delay)
            return posts

    return _StubFetcher()


def _make_failing_fetcher(exc: Exception) -> Fetcher:
    class _FailingFetcher(Fetcher):
        def fetch(self, query: FetchQuery) -> List[FetchedPost]:
            raise exc

    return _FailingFetcher()


def _post(post_id: str) -> FetchedPost:
    return FetchedPost(
        source="test",
        item_type="post",
        id=post_id,
        title=f"title {post_id}",
        text=f"text {post_id}",
        author="someone",
        url=f"https://example.com/{post_id}",
        created_at=datetime.now(timezone.utc),
    )


def test_all_source_fetches_both(tmp_path: Path, monkeypatch):
    """source="all" must fetch from both GitHub and Hacker News and
    combine their results - 10 distinct posts from each source, 20
    total, none dropped.
    """
    import src.pipeline.pipeline as pipeline_module

    github_posts = [_post(f"github-{i}") for i in range(10)]
    hn_posts = [_post(f"hn-{i}") for i in range(10)]

    def _stub_get_fetcher(config, *, source="reddit", force_mock=False):
        if source == "github":
            return _make_fetcher(github_posts)
        if source == "hackernews":
            return _make_fetcher(hn_posts)
        raise AssertionError(f"unexpected source: {source}")

    monkeypatch.setattr(pipeline_module, "get_fetcher", _stub_get_fetcher)

    config = PipelineConfig(
        source="all", keyword="invoicing", post_limit=20, output_dir=tmp_path, ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    result = Pipeline(config).run()

    assert result.summary.posts_fetched == 20


def test_all_source_parallel_execution(tmp_path: Path, monkeypatch):
    """Both sources must be fetched simultaneously (ThreadPoolExecutor),
    not sequentially - two 1-second fetches should take ~1s total, not
    ~2s, or _fetch_all_sources has silently regressed to a sequential loop.
    """
    import src.pipeline.pipeline as pipeline_module

    def _stub_get_fetcher(config, *, source="reddit", force_mock=False):
        return _make_fetcher([_post(f"{source}-1")], delay=1.0)

    monkeypatch.setattr(pipeline_module, "get_fetcher", _stub_get_fetcher)

    config = PipelineConfig(
        source="all", keyword="invoicing", post_limit=10, output_dir=tmp_path, ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    start = time.time()
    Pipeline(config).run()
    elapsed = time.time() - start

    assert elapsed < 2.0  # would be >= 2.0 if the two 1s fetches ran sequentially


def test_one_source_failure_continues(tmp_path: Path, monkeypatch):
    """A completely unexpected failure from one source (not a FetcherError
    - already covered by self._fetch()'s own retry/error-recording - but
    a genuine bug/exception inside get_fetcher() or a fetcher's own
    internals) must not prevent the other source's real results from
    coming through, and must not raise out of run().
    """
    import src.pipeline.pipeline as pipeline_module

    hn_posts = [_post(f"hn-{i}") for i in range(10)]

    def _stub_get_fetcher(config, *, source="reddit", force_mock=False):
        if source == "github":
            return _make_failing_fetcher(RuntimeError("simulated unexpected failure"))
        if source == "hackernews":
            return _make_fetcher(hn_posts)
        raise AssertionError(f"unexpected source: {source}")

    monkeypatch.setattr(pipeline_module, "get_fetcher", _stub_get_fetcher)

    config = PipelineConfig(
        source="all", keyword="invoicing", post_limit=20, output_dir=tmp_path, ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    result = Pipeline(config).run()  # must not raise

    assert result.summary.succeeded is True
    assert result.summary.posts_fetched == 10
    assert any("github" in e.lower() for e in result.summary.errors)


def test_single_source_unchanged(tmp_path: Path, monkeypatch):
    """source="github" (not "all") must still call get_fetcher exactly
    once, for "github" only - the pre-existing single-source path is
    untouched by the multi-source addition.
    """
    import src.pipeline.pipeline as pipeline_module

    calls: List[str] = []

    def _stub_get_fetcher(config, *, source="reddit", force_mock=False):
        calls.append(source)
        return _make_fetcher([_post("issue-1")])

    monkeypatch.setattr(pipeline_module, "get_fetcher", _stub_get_fetcher)

    config = PipelineConfig(
        source="github", keyword="invoicing", post_limit=5, output_dir=tmp_path, ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    result = Pipeline(config).run()

    assert calls == ["github"]
    assert result.summary.posts_fetched == 1


def test_oversample_split_between_sources(tmp_path: Path, monkeypatch):
    """num_reports-driven oversampling for source="all" must split the
    combined fetch target evenly across the two active sources, not
    request the full target from each independently. calculate_fetch_limit(10)
    is 30 (3x multiplier for a small request, see calculate_fetch_limit's
    own docstring) - split across 2 sources, each FetchQuery.limit is 15,
    so the two sources' results sum back to the original 30-discussion
    combined target.

    post_limit is deliberately set equal to that same 30 (not left at a
    generous default) so _should_oversample's own "still has headroom
    under post_limit" check is false regardless of how few clusters this
    test's minimal stub data produces - this isolates the *initial*
    fetch's split from the separate (and separately-covered, by
    test_one_source_failure_continues/test_all_source_fetches_both's own
    non-oversampling setup) retry-round behavior.
    """
    import src.pipeline.pipeline as pipeline_module

    limits_seen: List[int] = []

    def _stub_get_fetcher(config, *, source="reddit", force_mock=False):
        return _make_fetcher([_post(f"{source}-1")], calls=limits_seen)

    monkeypatch.setattr(pipeline_module, "get_fetcher", _stub_get_fetcher)

    assert calculate_fetch_limit(10) == 30
    config = PipelineConfig(
        source="all", keyword="invoicing", post_limit=30, num_reports=10, output_dir=tmp_path, ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    Pipeline(config).run()

    assert limits_seen == [15, 15]


def test_combined_discussions_deduplicated(tmp_path: Path, monkeypatch):
    """The exact same discussion (same FetchedPost.id) returned by both
    sources must appear only once in the combined, analyzed result -
    _fetch_all_sources merges via the same _merge_posts() dedup helper
    the oversample-retry path already relies on.
    """
    import src.pipeline.pipeline as pipeline_module

    shared_post = _post("shared-1")

    def _stub_get_fetcher(config, *, source="reddit", force_mock=False):
        return _make_fetcher([shared_post])

    monkeypatch.setattr(pipeline_module, "get_fetcher", _stub_get_fetcher)

    config = PipelineConfig(
        source="all", keyword="invoicing", post_limit=20, output_dir=tmp_path, ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    result = Pipeline(config).run()

    assert result.summary.posts_fetched == 1


# --- _CountingAIProvider -----------------------------------------------------


class _StubAIProvider(AIProvider):
    def check_connection(self) -> None:
        return

    def generate_text(self, prompt: str) -> str:
        return f"response to: {prompt}"


def test_counting_provider_counts_generate_text_calls():
    counting = _CountingAIProvider(_StubAIProvider())
    assert counting.call_count == 0

    counting.generate_text("a")
    counting.generate_text("b")
    counting.generate_text("c")

    assert counting.call_count == 3


def test_counting_provider_passes_through_response():
    counting = _CountingAIProvider(_StubAIProvider())
    assert counting.generate_text("hello") == "response to: hello"


# --- fetch retry -------------------------------------------------------------


class _AlwaysFailsFetcher(Fetcher):
    def __init__(self) -> None:
        self.attempts = 0

    def fetch(self, query: FetchQuery) -> List[FetchedPost]:
        self.attempts += 1
        raise FetcherError("simulated transient failure")


class _FailsTwiceThenSucceedsFetcher(Fetcher):
    def __init__(self) -> None:
        self.attempts = 0

    def fetch(self, query: FetchQuery) -> List[FetchedPost]:
        self.attempts += 1
        if self.attempts < 3:
            raise FetcherError("simulated transient failure")
        return []


def test_fetch_retry_gives_up_after_max_attempts():
    fetcher = _AlwaysFailsFetcher()
    with pytest.raises(FetcherError):
        _fetch_with_retry(fetcher, FetchQuery(community="x"))
    assert fetcher.attempts == 3  # _FETCH_MAX_ATTEMPTS


def test_fetch_retry_succeeds_after_transient_failures():
    fetcher = _FailsTwiceThenSucceedsFetcher()
    result = _fetch_with_retry(fetcher, FetchQuery(community="x"))
    assert result == []
    assert fetcher.attempts == 3


# --- full pipeline runs, fully offline ---------------------------------------


def test_full_pipeline_offline_mock_never_raises_and_produces_summary(tmp_path: Path):
    """MockAIProvider returns schema-valid JSON (with real, verbatim
    quotes pulled from each post's own text), so every extraction now
    succeeds in one call with no retry, and clustering runs the real
    AI-assisted path rather than falling back to lexical overlap. The
    pipeline must still complete, still save a report and a summary,
    and still report succeeded=True.

    cache_path is isolated to tmp_path: valid mock JSON is now
    cacheable (unlike before this fix), so without isolation this test
    would read/write the project's real, persistent .cache/ file (see
    PipelineConfig.cache_path's repo-relative default) and its
    ai_calls_made assertion would depend on prior test runs.
    """
    config = PipelineConfig(
        subreddit="test",
        post_limit=3,
        output_dir=tmp_path,
        ai_provider="mock",
        force_mock_fetch=True,
        cache_path=tmp_path / "ai_cache.json",
    )

    result = Pipeline(config).run()

    assert result.summary.succeeded is True
    assert result.summary.posts_fetched == 3
    assert result.summary.posts_analyzed == 3  # every extraction succeeds against valid mock JSON
    # One extraction call per post (no retry needed) + one clustering call.
    assert result.summary.ai_calls_made == 4
    assert len(result.summary.errors) == 0
    assert result.summary.report_path is not None
    assert result.summary.report_path.exists()
    assert result.report is not None


def test_pipeline_timing_logs_appear(tmp_path: Path, caplog):
    config = PipelineConfig(
        subreddit="test",
        post_limit=3,
        output_dir=tmp_path,
        ai_provider="mock",
        force_mock_fetch=True,
        cache_path=tmp_path / "ai_cache.json",
    )

    with caplog.at_level("INFO", logger="src.pipeline.pipeline"):
        Pipeline(config).run()

    assert "⏱ Fetch:" in caplog.text
    assert "⏱ Extract:" in caplog.text
    assert "⏱ Cluster:" in caplog.text
    assert "⏱ Total:" in caplog.text


def test_pipeline_saves_valid_execution_summary_json(tmp_path: Path):
    config = PipelineConfig(
        subreddit="test", post_limit=2, output_dir=tmp_path, ai_provider="mock", force_mock_fetch=True
    )

    Pipeline(config).run()

    summary_files = list(tmp_path.glob("pipeline_run_*.json"))
    assert len(summary_files) == 1
    data = json.loads(summary_files[0].read_text(encoding="utf-8"))
    assert data["posts_fetched"] == 2
    assert data["succeeded"] is True
    assert "start_time" in data and "end_time" in data and "duration_seconds" in data


def test_pipeline_report_format_terminal_only_does_not_save_markdown(tmp_path: Path):
    config = PipelineConfig(
        subreddit="test",
        post_limit=1,
        output_dir=tmp_path,
        ai_provider="mock",
        force_mock_fetch=True,
        report_format="terminal",
    )

    result = Pipeline(config).run()

    assert result.summary.report_path is None
    assert not list(tmp_path.glob("report_*.md"))


def test_pipeline_never_raises_on_unexpected_internal_failure(tmp_path: Path, monkeypatch):
    """The one deliberate broad except in this codebase — confirm it
    actually catches an arbitrary unexpected exception rather than
    letting it propagate, and records it honestly as a failure.
    """
    import src.pipeline.pipeline as pipeline_module

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated unexpected bug")

    monkeypatch.setattr(pipeline_module, "generate_report", _boom)

    config = PipelineConfig(
        subreddit="test", post_limit=1, output_dir=tmp_path, ai_provider="mock", force_mock_fetch=True
    )

    result = Pipeline(config).run()  # must not raise

    assert result.summary.succeeded is False
    assert any("simulated unexpected bug" in e for e in result.summary.errors)
    assert result.report is None


# --- Progress callback (Pipeline.run(on_progress=...)) ------------------------------


def test_progress_callback_fires(tmp_path: Path):
    calls: List[tuple] = []

    def on_progress(stage: str, message: str, percent: int) -> None:
        calls.append((stage, message, percent))

    config = PipelineConfig(
        subreddit="test", post_limit=3, output_dir=tmp_path, ai_provider="mock", force_mock_fetch=True
    )
    Pipeline(config).run(on_progress=on_progress)

    assert len(calls) >= 5
    assert all(isinstance(stage, str) and isinstance(message, str) and isinstance(percent, int) for stage, message, percent in calls)


def test_progress_percent_increases(tmp_path: Path):
    percents: List[int] = []

    def on_progress(stage: str, message: str, percent: int) -> None:
        percents.append(percent)

    config = PipelineConfig(
        subreddit="test", post_limit=5, output_dir=tmp_path, ai_provider="mock", force_mock_fetch=True
    )
    Pipeline(config).run(on_progress=on_progress)

    assert percents == sorted(percents)  # never decreases
    assert percents[0] >= 1
    assert percents[-1] == 100


def test_no_callback_doesnt_break(tmp_path: Path):
    config = PipelineConfig(
        subreddit="test", post_limit=3, output_dir=tmp_path, ai_provider="mock", force_mock_fetch=True
    )

    result = Pipeline(config).run()  # on_progress omitted entirely - must not raise

    assert result.summary.succeeded is True


def test_progress_callback_reports_correct_final_counts(tmp_path: Path):
    events: List[tuple] = []

    def on_progress(stage: str, message: str, percent: int) -> None:
        events.append((stage, message, percent))

    config = PipelineConfig(
        subreddit="test", post_limit=3, output_dir=tmp_path, ai_provider="mock", force_mock_fetch=True
    )
    result = Pipeline(config).run(on_progress=on_progress)

    assert events[0][2] == 5  # fetch start
    assert events[-1] == ("done", f"🎉 Done! Found {len(result.report.top_opportunities)} opportunities in {result.summary.duration_seconds:.1f}s", 100)
    stages_seen = {stage for stage, _, _ in events}
    assert stages_seen == {"fetch", "analyze", "cluster", "verify", "report", "done"}


def test_progress_callback_not_fired_during_oversample_round(tmp_path: Path, monkeypatch):
    """Documented, deliberate limitation (see run()'s own docstring):
    only the main pass reports progress, not a GitHub num_reports
    oversample round - this proves that choice actually holds, not
    just that it's written down.
    """
    fetcher = _AvailablePostsFetcher(available=3)
    _patch_github_fetch_and_clustering(monkeypatch, fetcher, MockAIProvider())

    events: List[tuple] = []

    def on_progress(stage: str, message: str, percent: int) -> None:
        events.append((stage, message, percent))

    config = PipelineConfig(
        source="github",
        keyword="invoicing",
        post_limit=50,
        num_reports=10,  # more than the 3 available -> triggers exactly one oversample round
        output_dir=tmp_path,
        ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )
    Pipeline(config).run(on_progress=on_progress)

    assert fetcher.calls == [30, 50]  # confirms the oversample round really happened
    percents = [percent for _, _, percent in events]
    assert percents == sorted(percents)  # still never decreases despite the extra round


# --- CLI ----------------------------------------------------------------------


def test_cli_mock_flag_runs_fully_offline_end_to_end(tmp_path: Path):
    from src.pipeline.runner import main

    exit_code = main(["--mock", "--limit", "2", "--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert list(tmp_path.glob("report_*.md"))
    assert list(tmp_path.glob("pipeline_run_*.json"))


# --- Task 7: CLI validation ---------------------------------------------------


@pytest.mark.parametrize("bad_limit", ["0", "-5", "abc", "3.5"])
def test_cli_rejects_invalid_limit_with_clean_error(bad_limit: str, capsys):
    from src.pipeline.runner import main

    with pytest.raises(SystemExit) as exc_info:
        main(["--mock", "--limit", bad_limit])

    assert exc_info.value.code == 2  # argparse's standard "bad usage" exit code
    captured = capsys.readouterr()
    assert "--limit" in captured.err


def test_cli_rejects_blank_subreddit_with_clean_error(capsys):
    from src.pipeline.runner import main

    with pytest.raises(SystemExit) as exc_info:
        main(["--mock", "--subreddit", "   "])

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "--subreddit" in captured.err


def test_cli_accepts_valid_positive_limit():
    from src.pipeline.runner import _positive_int

    assert _positive_int("1") == 1
    assert _positive_int("25") == 25


def test_cli_help_exits_zero_and_lists_all_flags(capsys):
    from src.pipeline.runner import main

    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    for flag in ["--subreddit", "--keyword", "--limit", "--output-dir", "--ai-provider", "--format", "--mock", "--verbose"]:
        assert flag in captured.out


# --- Task 7: logging configuration --------------------------------------------


def test_configure_logging_default_suppresses_third_party_but_shows_our_own():
    import logging

    from src.pipeline.runner import _configure_logging

    _configure_logging(verbose=False)

    assert logging.getLogger().getEffectiveLevel() == logging.WARNING  # third-party stays quiet
    assert logging.getLogger("src").getEffectiveLevel() == logging.INFO  # our own logs show


def test_configure_logging_verbose_shows_everything():
    import logging

    from src.pipeline.runner import _configure_logging

    _configure_logging(verbose=True)

    assert logging.getLogger().getEffectiveLevel() == logging.DEBUG
    assert logging.getLogger("src").getEffectiveLevel() == logging.DEBUG
