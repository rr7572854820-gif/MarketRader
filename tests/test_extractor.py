"""Tests for src/insights/extractor.py's own logic: quote verification,
JSON parse/retry behavior, score clamping, and enum coercion with
conservative fallback defaults.

This module had zero dedicated unit tests before Task 9 despite being
one of the densest pieces of pure business logic in the project -
flagged as an open gap in TODO.md since Task 4. All tests here use a
stub AIProvider (never a real Gemini call), the same pattern already
established in tests/test_cache.py.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import List, Optional

import pytest

from src.ai.base import AIProvider, AIProviderError
from src.insights.extractor import Extractor, InsightExtractionError
from src.insights.models import ConfidenceLevel, Sentiment
from src.models import FetchedPost

_SOURCE_TEXT = (
    "I run a small subscription business and every month I spend hours "
    "manually matching Stripe payouts against QuickBooks."
)


def _make_post(text: str = _SOURCE_TEXT, title: Optional[str] = "Reconciliation is painful") -> FetchedPost:
    return FetchedPost(
        source="mock",
        item_type="post",
        id="post-1",
        title=title,
        text=text,
        author="someone",
        url="mock://sample/post-1",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        is_mock=True,
    )


def _valid_data(**overrides) -> dict:
    data = {
        "primary_pain_point": {
            "description": "Manual reconciliation wastes hours",
            "evidence_quote": "I run a small subscription business",
        },
        "secondary_pain_points": [],
        "user_persona": "Small business owner",
        "feature_requests": [],
        "buying_signals": [],
        "emotional_sentiment": "Frustrated",
        "urgency_score": 5,
        "opportunity_score": 50,
        "confidence": "Strong",
        "startup_opportunity": "An automation tool",
        "supporting_evidence": [],
    }
    data.update(overrides)
    return data


class _FixedResponseProvider(AIProvider):
    """Always returns the same response text; counts calls."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    def check_connection(self) -> None:
        return

    def generate_text(self, prompt: str) -> str:
        self.calls += 1
        return self.response


class _SequenceResponseProvider(AIProvider):
    """Returns one response per call, in order; counts calls."""

    def __init__(self, responses: List[str]) -> None:
        self._responses = responses
        self.calls = 0

    def check_connection(self) -> None:
        return

    def generate_text(self, prompt: str) -> str:
        response = self._responses[self.calls]
        self.calls += 1
        return response


class _ErrorProvider(AIProvider):
    def __init__(self) -> None:
        self.calls = 0

    def check_connection(self) -> None:
        return

    def generate_text(self, prompt: str) -> str:
        self.calls += 1
        raise AIProviderError("simulated provider failure")


# --- Happy path -----------------------------------------------------------------


def test_extract_builds_insight_with_verified_primary_quote():
    provider = _FixedResponseProvider(json.dumps(_valid_data()))
    insight = Extractor(provider).extract(_make_post())

    assert insight.source_post_id == "post-1"
    assert insight.primary_pain_point.evidence_quote == "I run a small subscription business"
    assert insight.confidence == ConfidenceLevel.STRONG
    assert insight.emotional_sentiment == Sentiment.FRUSTRATED
    assert provider.calls == 1


def test_markdown_fenced_json_response_is_parsed():
    fenced = "```json\n" + json.dumps(_valid_data()) + "\n```"
    provider = _FixedResponseProvider(fenced)
    insight = Extractor(provider).extract(_make_post())

    assert insight.primary_pain_point.description == "Manual reconciliation wastes hours"


# --- Quote verification (the core non-fabrication guardrail) --------------------


def test_primary_pain_point_with_unverifiable_quote_raises():
    data = _valid_data(primary_pain_point={"description": "Fabricated", "evidence_quote": "this text is not in the source"})
    provider = _FixedResponseProvider(json.dumps(data))

    with pytest.raises(InsightExtractionError):
        Extractor(provider).extract(_make_post())

    assert provider.calls == 2  # both attempts made, same unverifiable quote both times


def test_secondary_pain_point_with_unverifiable_quote_is_dropped_not_fatal():
    data = _valid_data(
        secondary_pain_points=[
            {"description": "Real secondary", "evidence_quote": "matching Stripe payouts"},
            {"description": "Fabricated secondary", "evidence_quote": "definitely not in the source text"},
        ]
    )
    provider = _FixedResponseProvider(json.dumps(data))
    insight = Extractor(provider).extract(_make_post())

    assert len(insight.secondary_pain_points) == 1
    assert insight.secondary_pain_points[0].description == "Real secondary"


def test_buying_signals_filter_out_unverifiable_quotes():
    data = _valid_data(buying_signals=["manually matching Stripe payouts", "a quote that was never said"])
    provider = _FixedResponseProvider(json.dumps(data))
    insight = Extractor(provider).extract(_make_post())

    assert insight.buying_signals == ["manually matching Stripe payouts"]


def test_supporting_evidence_filter_out_unverifiable_quotes():
    data = _valid_data(supporting_evidence=["every month I spend hours", "invented supporting text"])
    provider = _FixedResponseProvider(json.dumps(data))
    insight = Extractor(provider).extract(_make_post())

    assert insight.supporting_evidence == ["every month I spend hours"]


# --- JSON parse / retry behavior -------------------------------------------------


def test_malformed_json_retries_once_then_succeeds():
    provider = _SequenceResponseProvider(["not json at all", json.dumps(_valid_data())])
    insight = Extractor(provider).extract(_make_post())

    assert insight.primary_pain_point.description == "Manual reconciliation wastes hours"
    assert provider.calls == 2


def test_malformed_json_both_attempts_exhausts_retries_and_raises():
    provider = _FixedResponseProvider("still not json")

    with pytest.raises(InsightExtractionError):
        Extractor(provider).extract(_make_post())

    assert provider.calls == 2


def test_ai_provider_error_is_not_retried_and_wraps_immediately():
    provider = _ErrorProvider()

    with pytest.raises(InsightExtractionError):
        Extractor(provider).extract(_make_post())

    assert provider.calls == 1  # a provider-level failure is not retried by Extractor itself


# --- Score clamping and enum coercion --------------------------------------------


@pytest.mark.parametrize(
    "raw_urgency,expected",
    [(999, 10), (-5, 1), ("not a number", 1), (7, 7)],
)
def test_urgency_score_is_clamped_to_1_10(raw_urgency, expected):
    data = _valid_data(urgency_score=raw_urgency)
    provider = _FixedResponseProvider(json.dumps(data))
    insight = Extractor(provider).extract(_make_post())

    assert insight.urgency_score == expected


@pytest.mark.parametrize(
    "raw_opportunity,expected",
    [(500, 100), (-1, 1), ("nonsense", 1), (42, 42)],
)
def test_opportunity_score_is_clamped_to_1_100(raw_opportunity, expected):
    data = _valid_data(opportunity_score=raw_opportunity)
    provider = _FixedResponseProvider(json.dumps(data))
    insight = Extractor(provider).extract(_make_post())

    assert insight.opportunity_score == expected


def test_unrecognized_confidence_value_falls_back_to_weak():
    data = _valid_data(confidence="Extremely Confident")
    provider = _FixedResponseProvider(json.dumps(data))
    insight = Extractor(provider).extract(_make_post())

    assert insight.confidence == ConfidenceLevel.WEAK


def test_unrecognized_sentiment_falls_back_to_neutral():
    data = _valid_data(emotional_sentiment="Ecstatic")
    provider = _FixedResponseProvider(json.dumps(data))
    insight = Extractor(provider).extract(_make_post())

    assert insight.emotional_sentiment == Sentiment.NEUTRAL


def test_feature_requests_list_filters_blank_entries():
    data = _valid_data(feature_requests=["Real request", "   ", "", "Another real one"])
    provider = _FixedResponseProvider(json.dumps(data))
    insight = Extractor(provider).extract(_make_post())

    assert insight.feature_requests == ["Real request", "Another real one"]


# --- extract_all_parallel ---------------------------------------------------------


def _make_posts(n: int, fail_indices: frozenset = frozenset()) -> List[FetchedPost]:
    posts = []
    for i in range(n):
        text = f"{_SOURCE_TEXT} FAIL_MARKER_{i}" if i in fail_indices else _SOURCE_TEXT
        posts.append(
            FetchedPost(
                source="mock",
                item_type="post",
                id=f"post-{i}",
                title="Reconciliation is painful",
                text=text,
                author="someone",
                url=f"mock://sample/post-{i}",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                is_mock=True,
            )
        )
    return posts


class _MarkerBasedProvider(AIProvider):
    """Returns valid extraction JSON normally, but malformed JSON (both
    retry attempts - see Extractor._MAX_ATTEMPTS) for any prompt
    containing "FAIL_MARKER" - lets a test control exactly which posts
    succeed/fail through the real extract()/extract_all_parallel() path,
    not by mocking internal methods directly.
    """

    def __init__(self) -> None:
        self.calls = 0

    def check_connection(self) -> None:
        return

    def generate_text(self, prompt: str) -> str:
        self.calls += 1
        if "FAIL_MARKER" in prompt:
            return "not valid json"
        return json.dumps(_valid_data())


def test_extract_all_parallel_success():
    provider = _FixedResponseProvider(json.dumps(_valid_data()))
    posts = _make_posts(10)

    insights = Extractor(provider).extract_all_parallel(posts)

    assert len(insights) == 10


def test_extract_batch_size_respected():
    provider = _FixedResponseProvider(json.dumps(_valid_data()))
    posts = _make_posts(12)
    batch_completions: List[int] = []

    Extractor(provider).extract_all_parallel(
        posts, on_batch_complete=lambda done, total: batch_completions.append(done)
    )

    # Cumulative counts after each batch: 5, 10, 12 -> batches of 5, 5, 2 - proves
    # BATCH_SIZE (5) was respected without inspecting thread-pool internals directly.
    assert batch_completions == [5, 10, 12]


def test_extract_failed_items_skipped():
    provider = _MarkerBasedProvider()
    posts = _make_posts(5, fail_indices=frozenset({1, 3}))

    insights = Extractor(provider).extract_all_parallel(posts)  # must not raise

    assert len(insights) == 3


# --- extract_parallel_multi_key ---------------------------------------------------


class _RecordingProvider(AIProvider):
    """Like _FixedResponseProvider, but also records every post id it
    was asked to extract (parsed out of the prompt via the post's own
    title, which build_extraction_prompt embeds verbatim) - lets a test
    verify not just *how many* calls a provider got, but *which* posts
    it actually received, without reaching into extract_parallel_multi_key's
    own internals.
    """

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0
        self.received_titles: List[str] = []

    def check_connection(self) -> None:
        return

    def generate_text(self, prompt: str) -> str:
        self.calls += 1
        self.received_titles.append(prompt)
        return self.response


class _SlowResponseProvider(AIProvider):
    """Like _FixedResponseProvider, but sleeps `delay` seconds before
    each response - for test_parallel_faster_than_sequential, where
    the whole point is measuring wall-clock time.
    """

    def __init__(self, response: str, delay: float) -> None:
        self.response = response
        self.delay = delay
        self.calls = 0

    def check_connection(self) -> None:
        return

    def generate_text(self, prompt: str) -> str:
        self.calls += 1
        time.sleep(self.delay)
        return self.response


def _make_titled_posts(n: int) -> List[FetchedPost]:
    """Like _make_posts, but each post gets a distinct, identifiable
    title ("item-0", "item-1", ...) baked into the prompt - lets
    _RecordingProvider's captured prompts be matched back to a specific
    post index for the round-robin distribution assertion. Deliberately
    a different marker text ("item-N") than the post id/url ("post-N")
    below, so parsing the title back out of the prompt can't accidentally
    match the url's own "post-N" substring instead.
    """
    posts = []
    for i in range(n):
        posts.append(
            FetchedPost(
                source="mock",
                item_type="post",
                id=f"post-{i}",
                title=f"item-{i}",
                text=_SOURCE_TEXT,
                author="someone",
                url=f"mock://sample/post-{i}",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                is_mock=True,
            )
        )
    return posts


def test_parallel_extraction_distributes():
    providers = [_RecordingProvider(json.dumps(_valid_data())) for _ in range(3)]
    posts = _make_titled_posts(9)

    insights = Extractor(providers[0]).extract_parallel_multi_key(posts, providers)

    assert len(insights) == 9
    assert [p.calls for p in providers] == [3, 3, 3]
    # Round-robin: post i goes to provider i % 3 - item-0/3/6 to
    # provider 0, item-1/4/7 to provider 1, item-2/5/8 to provider 2.
    # Anchored on the literal "Discussion title: item-" prefix
    # (build_extraction_prompt's own format), not a bare "item-" split -
    # each post's url also independently contains "post-N", so a looser
    # match risks picking up the wrong substring.
    anchor = "Discussion title: item-"
    for key_idx, provider in enumerate(providers):
        received_indices = sorted(
            int(prompt.split(anchor, 1)[1].split("\n", 1)[0]) for prompt in provider.received_titles if anchor in prompt
        )
        assert received_indices == [key_idx, key_idx + 3, key_idx + 6]


def test_parallel_faster_than_sequential():
    providers = [_SlowResponseProvider(json.dumps(_valid_data()), delay=0.1) for _ in range(3)]
    posts = _make_posts(9)  # 3 per provider

    start = time.time()
    insights = Extractor(providers[0]).extract_parallel_multi_key(posts, providers)
    elapsed = time.time() - start

    assert len(insights) == 9
    assert elapsed < 0.5  # 3 providers x 3 sequential calls each (0.3s) run concurrently
    # Sequential baseline (a single provider handling all 9 one at a
    # time) would be ~0.9s - not run for real here (would slow the
    # suite down for no extra signal), but the arithmetic is what
    # motivates the < 0.5s threshold above.


def test_single_key_fallback():
    provider = _FixedResponseProvider(json.dumps(_valid_data()))
    posts = _make_posts(6)

    insights = Extractor(provider).extract_parallel_multi_key(posts, [provider])  # must not raise

    assert len(insights) == 6
    assert provider.calls == 6


def test_failed_extraction_skipped():
    failing = _ErrorProvider()
    working = [_FixedResponseProvider(json.dumps(_valid_data())) for _ in range(2)]
    providers = [failing, *working]
    posts = _make_posts(9)  # 3 per provider - failing's 3 must all come back as skipped

    insights = Extractor(providers[0]).extract_parallel_multi_key(posts, providers)  # must not raise

    assert len(insights) == 6  # 9 total - 3 that failing's provider couldn't extract
    assert failing.calls == 3
    assert working[0].calls == 3
    assert working[1].calls == 3


def test_extract_delay_between_batches(monkeypatch):
    # Overrides tests/conftest.py's autouse BATCH_DELAY=0 (which exists
    # so the rest of the suite doesn't pay a real 1.5s per batch) with a
    # small-but-real, measurable value just for this test.
    monkeypatch.setattr(Extractor, "BATCH_DELAY", 0.05)
    provider = _FixedResponseProvider(json.dumps(_valid_data()))
    posts = _make_posts(10)  # 2 batches of 5 -> exactly one delay between them

    start = time.time()
    Extractor(provider).extract_all_parallel(posts)
    elapsed = time.time() - start

    assert elapsed >= 0.05  # the one delay between batch 1 and batch 2 happened
    assert elapsed < 0.05 * 3  # not also delayed after the last batch (would be ~2x this)
