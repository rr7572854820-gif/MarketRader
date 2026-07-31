"""Tests for src/ai/mock_provider.py's JSON-schema fix: MockAIProvider
must return JSON that Extractor and Aggregator actually accept, not
just "some JSON" - including passing Extractor's quote-verification
guardrail with real, verbatim text pulled from the prompt itself.

tests/test_ai_providers.py still covers check_connection and the
get_ai_provider factory branching; this file is scoped to the response
content itself.
"""

from __future__ import annotations

import json

from src.insights.extractor import Extractor
from src.insights.aggregator import Aggregator
from src.insights.prompts import build_clustering_prompt, build_extraction_prompt
from src.ai.mock_provider import MOCK_RESPONSE_PREFIX, MockAIProvider
from src.models import FetchedPost
from datetime import datetime, timezone

_TITLE = "Reconciliation is painful"
_TEXT = (
    "I run a small subscription business and every month I spend hours "
    "manually matching Stripe payouts against QuickBooks. It never "
    "matches cleanly."
)


def _make_post(title=_TITLE, text=_TEXT) -> FetchedPost:
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


# --- Extraction schema ------------------------------------------------------------


def test_extraction_response_is_valid_json_matching_extractor_schema():
    prompt = build_extraction_prompt(_TITLE, _TEXT, "mock://sample/post-1")
    response = MockAIProvider().generate_text(prompt)

    data = json.loads(response)  # must not raise

    assert set(data.keys()) == {
        "primary_pain_point",
        "secondary_pain_points",
        "user_persona",
        "feature_requests",
        "buying_signals",
        "emotional_sentiment",
        "urgency_score",
        "opportunity_score",
        "confidence",
        "startup_opportunity",
        "supporting_evidence",
    }
    assert set(data["primary_pain_point"].keys()) == {"description", "evidence_quote"}


def test_extraction_response_evidence_quote_is_verbatim_substring_of_source_text():
    prompt = build_extraction_prompt(_TITLE, _TEXT, "mock://sample/post-1")
    data = json.loads(MockAIProvider().generate_text(prompt))

    quote = data["primary_pain_point"]["evidence_quote"]
    assert quote  # non-empty
    assert quote in _TEXT


def test_extraction_response_speculative_fields_are_labeled_as_mock():
    prompt = build_extraction_prompt(_TITLE, _TEXT, "mock://sample/post-1")
    data = json.loads(MockAIProvider().generate_text(prompt))

    assert data["user_persona"].startswith(MOCK_RESPONSE_PREFIX)
    assert data["startup_opportunity"].startswith(MOCK_RESPONSE_PREFIX)
    assert data["primary_pain_point"]["description"].startswith(MOCK_RESPONSE_PREFIX)


def test_extraction_response_end_to_end_through_real_extractor():
    """The actual integration this bug broke: Extractor.extract() must
    succeed against MockAIProvider's own output, in one call, with no
    retry needed.
    """
    provider = MockAIProvider()
    insight = Extractor(provider).extract(_make_post())

    assert insight.primary_pain_point.evidence_quote in _TEXT
    assert insight.confidence.value == "Weak"


# --- Clustering schema -------------------------------------------------------------


def test_clustering_response_is_valid_json_matching_aggregator_schema():
    items = [("desc a", "quote a"), ("desc b", "quote b"), ("desc c", "quote c")]
    prompt = build_clustering_prompt(items)
    response = MockAIProvider().generate_text(prompt)

    data = json.loads(response)  # must not raise

    assert isinstance(data["clusters"], list)
    all_indices = sorted(i for c in data["clusters"] for i in c["member_indices"])
    assert all_indices == [0, 1, 2]  # every discussion accounted for exactly once


def test_clustering_response_end_to_end_uses_ai_path_not_lexical_fallback():
    """The actual integration this bug broke: a valid mock clustering
    response must be accepted by Aggregator as a real AI response,
    never triggering the lexical fallback.
    """
    from src.insights.models import ConfidenceLevel, DiscussionInsight, PainPoint, Sentiment

    insights = [
        DiscussionInsight(
            source_post_id=f"p{i}",
            source_url=f"mock://sample/p{i}",
            is_mock_source=True,
            primary_pain_point=PainPoint(description=f"pain {i}", evidence_quote=f"quote {i}"),
            secondary_pain_points=[],
            user_persona="Someone",
            feature_requests=[],
            buying_signals=[],
            emotional_sentiment=Sentiment.NEUTRAL,
            urgency_score=1,
            opportunity_score=1,
            confidence=ConfidenceLevel.WEAK,
            startup_opportunity="",
            supporting_evidence=[],
        )
        for i in range(3)
    ]

    agg = Aggregator(MockAIProvider())
    clusters = agg.aggregate(insights)

    assert agg.last_method == "ai"
    assert agg.last_fallback_reason is None
    assert len(clusters) == 3  # mock makes no merge judgment: singleton clusters
