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
