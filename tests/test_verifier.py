"""Tests for src/verification/verifier.py.

Covers the common verification failure modes named in the Task 4
requirements: quote mismatch, missing evidence, empty/malformed
claims, verifying against the wrong source, and an insight whose
source post is entirely missing from the input. All offline, zero API
cost — the whole point of a deterministic verifier is that it doesn't
need one.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.insights.models import ConfidenceLevel, DiscussionInsight, PainPoint, Sentiment
from src.models import FetchedPost
from src.verification.models import VerificationStatus
from src.verification.verifier import Verifier, VerificationError

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_post(post_id: str = "post-1", title: str = "", text: str = "") -> FetchedPost:
    return FetchedPost(
        source="mock",
        item_type="post",
        id=post_id,
        title=title or None,
        text=text,
        author="tester",
        url=f"mock://{post_id}",
        created_at=_NOW,
        score=1,
        is_mock=True,
    )


def make_insight(
    source_post_id: str = "post-1",
    primary_desc: str = "Users struggle with manual reconciliation.",
    primary_quote: str = "I spend hours every month reconciling payouts manually.",
    secondary=(),
    persona: str = "",
    feature_requests=(),
    buying_signals=(),
    supporting_evidence=(),
) -> DiscussionInsight:
    return DiscussionInsight(
        source_post_id=source_post_id,
        source_url=f"mock://{source_post_id}",
        is_mock_source=True,
        primary_pain_point=PainPoint(primary_desc, primary_quote),
        secondary_pain_points=list(secondary),
        user_persona=persona,
        feature_requests=list(feature_requests),
        buying_signals=list(buying_signals),
        emotional_sentiment=Sentiment.FRUSTRATED,
        urgency_score=5,
        opportunity_score=50,
        confidence=ConfidenceLevel.STRONG,
        startup_opportunity="",
        supporting_evidence=list(supporting_evidence),
    )


# --- Quote-bearing claims -----------------------------------------------


def test_exact_quote_match_is_verified():
    post = make_post(text="I spend hours every month reconciling payouts manually. It's awful.")
    insight = make_insight(primary_quote="I spend hours every month reconciling payouts manually.")

    result = Verifier().verify(insight, post)
    primary = next(fv for fv in result.field_verifications if fv.field_name == "primary_pain_point")

    assert primary.verification_status == VerificationStatus.VERIFIED
    assert primary.confidence == ConfidenceLevel.STRONG
    assert primary.supporting_quotes == ["I spend hours every month reconciling payouts manually."]


def test_quote_not_in_source_is_unverified_not_fabricated():
    """Simulates a corrupted/mismatched insight — the quote simply
    isn't in this post's text. Must never be marked Verified, and must
    never invent a supporting quote to paper over the gap.
    """
    post = make_post(text="This post is about something completely different.")
    insight = make_insight(primary_quote="I spend hours every month reconciling payouts manually.")

    result = Verifier().verify(insight, post)
    primary = next(fv for fv in result.field_verifications if fv.field_name == "primary_pain_point")

    assert primary.verification_status == VerificationStatus.UNVERIFIED
    assert primary.supporting_quotes == []  # never fabricated


def test_empty_quote_is_unverified():
    post = make_post(text="Some real text here.")
    insight = make_insight(primary_quote="")

    result = Verifier().verify(insight, post)
    primary = next(fv for fv in result.field_verifications if fv.field_name == "primary_pain_point")

    assert primary.verification_status == VerificationStatus.UNVERIFIED


def test_supporting_evidence_and_buying_signals_verified_independently():
    post = make_post(text="I would pay for this tomorrow. Also, it breaks every single day.")
    insight = make_insight(
        buying_signals=["I would pay for this tomorrow."],
        supporting_evidence=["it breaks every single day."],
    )

    result = Verifier().verify(insight, post)
    buying = next(fv for fv in result.field_verifications if fv.field_name == "buying_signal[0]")
    evidence = next(fv for fv in result.field_verifications if fv.field_name == "supporting_evidence[0]")

    assert buying.verification_status == VerificationStatus.VERIFIED
    assert evidence.verification_status == VerificationStatus.VERIFIED


# --- Speculative claims (no attached quote): persona, feature requests --


def test_persona_with_keyword_support_is_partial_not_verified():
    post = make_post(
        text="I run a small subscription business and handle all the bookkeeping myself every month."
    )
    insight = make_insight(persona="Small subscription business owner handling their own bookkeeping.")

    result = Verifier().verify(insight, post)
    persona = next(fv for fv in result.field_verifications if fv.field_name == "user_persona")

    assert persona.verification_status == VerificationStatus.PARTIAL
    assert persona.confidence == ConfidenceLevel.MODERATE
    assert persona.supporting_quotes  # some sentence was found
    # Persona can never reach Verified — there's no quote claim to confirm.


def test_persona_with_no_keyword_support_is_unverified():
    post = make_post(text="A completely unrelated sentence about kayaking.")
    insight = make_insight(persona="Enterprise CFO managing a multinational payments team.")

    result = Verifier().verify(insight, post)
    persona = next(fv for fv in result.field_verifications if fv.field_name == "user_persona")

    assert persona.verification_status == VerificationStatus.UNVERIFIED
    assert persona.supporting_quotes == []


def test_feature_request_verified_independently_per_item():
    post = make_post(text="I really wish there was automated reconciliation built in.")
    insight = make_insight(feature_requests=["automated reconciliation"])

    result = Verifier().verify(insight, post)
    fr = next(fv for fv in result.field_verifications if fv.field_name == "feature_request[0]")

    assert fr.verification_status == VerificationStatus.PARTIAL


# --- Misuse / safety checks ----------------------------------------------


def test_verifying_against_wrong_source_raises():
    post = make_post(post_id="post-2")
    insight = make_insight(source_post_id="post-1")

    with pytest.raises(VerificationError):
        Verifier().verify(insight, post)


def test_missing_source_post_never_silently_dropped():
    insight = make_insight(source_post_id="post-missing")

    report = Verifier().verify_all([insight], posts=[])  # no posts provided at all

    assert len(report.results) == 1  # insight is still represented, not dropped
    assert report.results[0].source_post_id == "post-missing"
    assert all(fv.verification_status == VerificationStatus.UNVERIFIED for fv in report.results[0].field_verifications)


# --- Rollups and report aggregation ---------------------------------------


def test_overall_status_is_worst_case_rollup():
    post = make_post(text="I spend hours every month reconciling payouts manually.")
    insight = make_insight(
        primary_quote="I spend hours every month reconciling payouts manually.",
        persona="Someone completely unrelated to anything in this text.",
    )

    result = Verifier().verify(insight, post)

    # primary is Verified but persona is Unverified -> overall must be Unverified, not averaged away
    assert result.overall_status == VerificationStatus.UNVERIFIED


def test_verification_report_counts_and_rate_across_multiple_insights():
    # Each insight here produces 2 field checks: primary_pain_point and
    # user_persona (persona is always checked, even when empty/unset —
    # an empty persona is correctly Unverified, not skipped).
    post_a = make_post(post_id="a", text="I spend hours every month reconciling payouts manually.")
    post_b = make_post(post_id="b", text="Something totally unrelated.")
    insight_a = make_insight(
        source_post_id="a", primary_quote="I spend hours every month reconciling payouts manually."
    )
    insight_b = make_insight(source_post_id="b", primary_quote="a quote that does not exist in post b")

    report = Verifier().verify_all([insight_a, insight_b], [post_a, post_b])

    assert report.total_claims == 4  # 2 insights x 2 checked fields each
    assert report.verified_count == 1  # only insight_a's primary_pain_point
    assert report.unverified_count == 3  # insight_a's empty persona, insight_b's mismatched quote, insight_b's empty persona
    assert report.verification_rate == 0.25
