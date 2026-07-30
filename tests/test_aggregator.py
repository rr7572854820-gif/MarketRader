"""Tests for src/insights/aggregator.py's own logic: AI-assisted
clustering, its fallback-to-lexical behavior on failure, the response
validation/dedup rules, the lexical Jaccard fallback itself, and
confidence-aggregation rules.

Zero dedicated unit tests existed for this module before Task 9 -
flagged as an open gap since Task 3.1 (which measured clustering
quality by hand, but never turned those measurements into pytest
cases). All tests here use a stub AIProvider, never a real Gemini call.
"""

from __future__ import annotations

import json

import pytest

from src.ai.base import AIProvider, AIProviderError
from src.insights.aggregator import Aggregator
from src.insights.models import ConfidenceLevel, DiscussionInsight, PainPoint, Sentiment


def _make_insight(
    post_id: str,
    description: str,
    evidence_quote: str = "some evidence",
    confidence: ConfidenceLevel = ConfidenceLevel.MODERATE,
    opportunity_score: int = 50,
    urgency_score: int = 5,
    supporting_evidence=None,
) -> DiscussionInsight:
    return DiscussionInsight(
        source_post_id=post_id,
        source_url=f"mock://sample/{post_id}",
        is_mock_source=True,
        primary_pain_point=PainPoint(description=description, evidence_quote=evidence_quote),
        secondary_pain_points=[],
        user_persona="Someone",
        feature_requests=[],
        buying_signals=[],
        emotional_sentiment=Sentiment.FRUSTRATED,
        urgency_score=urgency_score,
        opportunity_score=opportunity_score,
        confidence=confidence,
        startup_opportunity="",
        supporting_evidence=supporting_evidence or [],
    )


class _FixedResponseProvider(AIProvider):
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    def check_connection(self) -> None:
        return

    def generate_text(self, prompt: str) -> str:
        self.calls += 1
        return self.response


class _ErrorProvider(AIProvider):
    def check_connection(self) -> None:
        return

    def generate_text(self, prompt: str) -> str:
        raise AIProviderError("simulated clustering failure")


def _clusters_response(*groups) -> str:
    return json.dumps({"clusters": [{"label": f"group{i}", "member_indices": list(g)} for i, g in enumerate(groups)]})


# --- Basics -----------------------------------------------------------------------


def test_empty_insights_returns_empty_list():
    assert Aggregator(None).aggregate([]) == []


# --- AI-assisted clustering: happy path --------------------------------------------


def test_ai_clustering_groups_by_response_and_sets_last_method():
    insights = [_make_insight("p1", "reconciliation pain"), _make_insight("p2", "reconciliation pain, same thing")]
    provider = _FixedResponseProvider(_clusters_response([0, 1]))
    agg = Aggregator(provider)

    clusters = agg.aggregate(insights)

    assert len(clusters) == 1
    assert clusters[0].occurrence_count == 2
    assert agg.last_method == "ai"
    assert agg.last_fallback_reason is None


def test_ai_clustering_keeps_distinct_groups_separate():
    insights = [_make_insight("p1", "reconciliation pain"), _make_insight("p2", "onboarding confusion")]
    provider = _FixedResponseProvider(_clusters_response([0], [1]))

    clusters = Aggregator(provider).aggregate(insights)

    assert len(clusters) == 2
    assert {c.occurrence_count for c in clusters} == {1}


# --- AI-assisted clustering: fallback behavior --------------------------------------


def test_malformed_ai_response_falls_back_to_lexical_and_records_reason():
    insights = [_make_insight("p1", "reconciliation pain"), _make_insight("p2", "onboarding confusion")]
    provider = _FixedResponseProvider("not json at all")
    agg = Aggregator(provider)

    clusters = agg.aggregate(insights)

    assert agg.last_method == "lexical_fallback"
    assert agg.last_fallback_reason is not None
    assert len(clusters) == 2  # lexical fallback still produces a valid result


def test_ai_response_missing_clusters_key_falls_back():
    insights = [_make_insight("p1", "reconciliation pain")]
    provider = _FixedResponseProvider(json.dumps({"not_clusters": []}))
    agg = Aggregator(provider)

    agg.aggregate(insights)

    assert agg.last_method == "lexical_fallback"
    assert agg.last_fallback_reason is not None


def test_ai_provider_error_falls_back_to_lexical():
    insights = [_make_insight("p1", "reconciliation pain")]
    agg = Aggregator(_ErrorProvider())

    agg.aggregate(insights)

    assert agg.last_method == "lexical_fallback"
    assert "AIProviderError" in agg.last_fallback_reason


def test_no_ai_provider_uses_lexical_directly_with_no_fallback_reason():
    """Distinguishes 'no provider was ever given' from 'a provider was
    given and failed' - only the latter should populate a reason.
    """
    insights = [_make_insight("p1", "reconciliation pain")]
    agg = Aggregator(None)

    agg.aggregate(insights)

    assert agg.last_method == "lexical_fallback"
    assert agg.last_fallback_reason is None


# --- AI response validation / dedup rules -------------------------------------------


def test_ai_response_duplicate_index_first_occurrence_wins():
    insights = [_make_insight("p1", "a"), _make_insight("p2", "b"), _make_insight("p3", "c")]
    # index 0 appears in both groups; first group should keep it, second should not.
    provider = _FixedResponseProvider(_clusters_response([0, 1], [0, 2]))

    clusters = Aggregator(provider).aggregate(insights)
    all_members = [pid for c in clusters for i in c.insights for pid in [i.source_post_id]]

    assert sorted(all_members) == ["p1", "p2", "p3"]  # every insight appears exactly once total


def test_ai_response_out_of_range_index_is_dropped():
    insights = [_make_insight("p1", "a"), _make_insight("p2", "b")]
    provider = _FixedResponseProvider(_clusters_response([0, 99]))

    clusters = Aggregator(provider).aggregate(insights)
    all_members = {i.source_post_id for c in clusters for i in c.insights}

    assert all_members == {"p1", "p2"}  # p2 (index 1) becomes its own singleton, 99 is just dropped


def test_ai_response_index_never_mentioned_becomes_singleton():
    insights = [_make_insight("p1", "a"), _make_insight("p2", "b"), _make_insight("p3", "c")]
    provider = _FixedResponseProvider(_clusters_response([0, 1]))  # index 2 never mentioned

    clusters = Aggregator(provider).aggregate(insights)

    singleton = [c for c in clusters if c.occurrence_count == 1]
    assert len(singleton) == 1
    assert singleton[0].insights[0].source_post_id == "p3"


# --- Lexical fallback clustering (no AI provider) ------------------------------------


def test_lexical_fallback_merges_heavily_overlapping_keywords():
    insights = [
        _make_insight(
            "p1",
            "reconciling stripe payouts against quickbooks manually every month",
            evidence_quote="reconciling stripe payouts quickbooks",
        ),
        _make_insight(
            "p2",
            "reconciling stripe payouts against quickbooks manually every month too",
            evidence_quote="reconciling stripe payouts quickbooks",
        ),
    ]

    clusters = Aggregator(None).aggregate(insights)

    assert len(clusters) == 1
    assert clusters[0].occurrence_count == 2


def test_lexical_fallback_does_not_merge_dissimilar_insights():
    insights = [
        _make_insight("p1", "reconciling stripe payouts against quickbooks", evidence_quote="stripe payouts quickbooks"),
        _make_insight("p2", "no-code tools break on conditional logic", evidence_quote="conditional logic branching"),
    ]

    clusters = Aggregator(None).aggregate(insights)

    assert len(clusters) == 2


# --- Confidence aggregation ------------------------------------------------------------


def test_confidence_aggregation_strongest_wins():
    insights = [
        _make_insight("p1", "same pain", confidence=ConfidenceLevel.WEAK),
        _make_insight("p2", "same pain", confidence=ConfidenceLevel.STRONG),
    ]
    provider = _FixedResponseProvider(_clusters_response([0, 1]))

    clusters = Aggregator(provider).aggregate(insights)

    assert clusters[0].confidence == ConfidenceLevel.STRONG


def test_confidence_aggregation_multiple_weak_corroborating_insights_bumps_to_moderate():
    insights = [
        _make_insight("p1", "same pain", confidence=ConfidenceLevel.WEAK),
        _make_insight("p2", "same pain", confidence=ConfidenceLevel.WEAK),
    ]
    provider = _FixedResponseProvider(_clusters_response([0, 1]))

    clusters = Aggregator(provider).aggregate(insights)

    assert clusters[0].confidence == ConfidenceLevel.MODERATE


def test_single_weak_insight_cluster_stays_weak():
    insights = [_make_insight("p1", "isolated pain", confidence=ConfidenceLevel.WEAK)]
    provider = _FixedResponseProvider(_clusters_response([0]))

    clusters = Aggregator(provider).aggregate(insights)

    assert clusters[0].confidence == ConfidenceLevel.WEAK


# --- Ranking -----------------------------------------------------------------------------


def test_clusters_ranked_by_opportunity_score_descending():
    insights = [
        _make_insight("p1", "low value pain", opportunity_score=10),
        _make_insight("p2", "high value pain", opportunity_score=90),
    ]
    provider = _FixedResponseProvider(_clusters_response([0], [1]))

    clusters = Aggregator(provider).aggregate(insights)

    assert clusters[0].average_opportunity_score == 90
    assert clusters[1].average_opportunity_score == 10
