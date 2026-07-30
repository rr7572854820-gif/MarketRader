"""Tests for src/reporting/ — both the generator's logic and the
formatter's output. All offline, zero API cost, consistent with
test_verifier.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.insights.models import ConfidenceLevel, DiscussionInsight, OpportunityCluster, PainPoint, Sentiment
from src.models import FetchedPost
from src.reporting.formatter import format_markdown, format_terminal, save_markdown_file
from src.reporting.report_generator import generate_report
from src.verification.models import FieldVerification, InsightVerificationResult, VerificationReport, VerificationStatus

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_post(post_id: str) -> FetchedPost:
    return FetchedPost(
        source="mock", item_type="post", id=post_id, title=None, text="irrelevant for these tests",
        author="tester", url=f"mock://{post_id}", created_at=_NOW, score=1, is_mock=True,
    )


def make_insight(post_id: str, persona: str = "Small business owner") -> DiscussionInsight:
    return DiscussionInsight(
        source_post_id=post_id,
        source_url=f"mock://{post_id}",
        is_mock_source=True,
        primary_pain_point=PainPoint("A pain point", "the evidence quote"),
        secondary_pain_points=[],
        user_persona=persona,
        feature_requests=[],
        buying_signals=[],
        emotional_sentiment=Sentiment.FRUSTRATED,
        urgency_score=5,
        opportunity_score=80,
        confidence=ConfidenceLevel.STRONG,
        startup_opportunity="",
        supporting_evidence=[],
    )


def make_field(post_id: str, status: VerificationStatus, quotes=("the evidence quote",)) -> FieldVerification:
    return FieldVerification(
        field_name="primary_pain_point",
        claim_text="A pain point",
        verification_status=status,
        confidence=ConfidenceLevel.STRONG if status == VerificationStatus.VERIFIED else ConfidenceLevel.WEAK,
        supporting_quotes=list(quotes) if status == VerificationStatus.VERIFIED else [],
        source_discussion_ids=[post_id],
    )


def make_verification_report(results) -> VerificationReport:
    all_fields = [fv for r in results for fv in r.field_verifications]
    verified = sum(1 for fv in all_fields if fv.verification_status == VerificationStatus.VERIFIED)
    partial = sum(1 for fv in all_fields if fv.verification_status == VerificationStatus.PARTIAL)
    unverified = sum(1 for fv in all_fields if fv.verification_status == VerificationStatus.UNVERIFIED)
    total = len(all_fields)
    return VerificationReport(
        total_claims=total, verified_count=verified, partial_count=partial, unverified_count=unverified,
        verification_rate=(verified / total if total else 0.0), results=results,
    )


# --- report_generator.py --------------------------------------------------


def test_verification_rate_computed_per_cluster():
    post = make_post("p1")
    insight = make_insight("p1")
    cluster = OpportunityCluster(
        label="A pain point", occurrence_count=1, average_opportunity_score=80.0,
        average_urgency_score=5.0, confidence=ConfidenceLevel.STRONG, insights=[insight],
    )
    result = InsightVerificationResult("p1", [make_field("p1", VerificationStatus.VERIFIED)])
    report = generate_report([cluster], make_verification_report([result]), [post], "Mock AI provider")

    entry = report.top_opportunities[0]
    assert entry.verification_rate == 1.0
    assert entry.has_verification_data is True


def test_only_verified_quotes_surface_never_partial():
    """A Partial-status field's loosely-matched sentence must never
    appear in the report's supporting_quotes — only exact-match
    Verified quotes are trustworthy enough to publish.
    """
    post = make_post("p1")
    insight = make_insight("p1")
    cluster = OpportunityCluster(
        label="A pain point", occurrence_count=1, average_opportunity_score=80.0,
        average_urgency_score=5.0, confidence=ConfidenceLevel.STRONG, insights=[insight],
    )
    partial_field = FieldVerification(
        field_name="user_persona", claim_text="Small business owner",
        verification_status=VerificationStatus.PARTIAL, confidence=ConfidenceLevel.MODERATE,
        supporting_quotes=["some loosely related sentence"], source_discussion_ids=["p1"],
    )
    verified_field = make_field("p1", VerificationStatus.VERIFIED)
    result = InsightVerificationResult("p1", [verified_field, partial_field])
    report = generate_report([cluster], make_verification_report([result]), [post], "Mock AI provider")

    quotes = report.top_opportunities[0].supporting_quotes
    assert "the evidence quote" in quotes
    assert "some loosely related sentence" not in quotes


def test_no_verification_data_reported_honestly_not_as_zero_percent():
    post = make_post("p1")
    insight = make_insight("p1")
    cluster = OpportunityCluster(
        label="A pain point", occurrence_count=1, average_opportunity_score=80.0,
        average_urgency_score=5.0, confidence=ConfidenceLevel.STRONG, insights=[insight],
    )
    # verification report has no results at all for this post
    report = generate_report([cluster], make_verification_report([]), [post], "Mock AI provider")

    entry = report.top_opportunities[0]
    assert entry.has_verification_data is False
    assert entry.verification_rate == 0.0


def test_recommended_next_action_never_a_build_or_invest_verdict():
    """Guards the core architectural rule directly: no recommendation
    text may ever tell the user to build or invest — only research
    actions are allowed.
    """
    from src.reporting.report_generator import _recommend_next_action

    forbidden_words = ["build this", "you should invest", "go build", "definitely build", "this is a good business"]
    scenarios = [
        (ConfidenceLevel.STRONG, 0.9, True, 3),
        (ConfidenceLevel.WEAK, 0.2, True, 1),
        (ConfidenceLevel.MODERATE, 0.6, True, 2),
        (ConfidenceLevel.STRONG, 0.0, False, 1),
    ]
    for confidence, rate, has_data, freq in scenarios:
        text = _recommend_next_action(confidence, rate, has_data, freq).lower()
        for forbidden in forbidden_words:
            assert forbidden not in text


def test_customer_segment_uses_first_non_empty_persona_not_merged():
    post_a, post_b = make_post("a"), make_post("b")
    insight_a = make_insight("a", persona="")
    insight_b = make_insight("b", persona="Agency owner")
    cluster = OpportunityCluster(
        label="A pain point", occurrence_count=2, average_opportunity_score=80.0,
        average_urgency_score=5.0, confidence=ConfidenceLevel.STRONG, insights=[insight_a, insight_b],
    )
    report = generate_report([cluster], make_verification_report([]), [post_a, post_b], "Mock AI provider")

    assert report.top_opportunities[0].suggested_customer_segment == "Agency owner"


def test_empty_clusters_handled_gracefully():
    report = generate_report([], make_verification_report([]), [], "Mock AI provider")
    assert report.top_opportunities == []
    assert "no opportunity clusters" in report.executive_summary.lower() or "0" in report.executive_summary


# --- formatter.py -----------------------------------------------------------


def _sample_report():
    post = make_post("p1")
    insight = make_insight("p1")
    cluster = OpportunityCluster(
        label="Manual reconciliation is painful", occurrence_count=2, average_opportunity_score=85.0,
        average_urgency_score=7.0, confidence=ConfidenceLevel.STRONG, insights=[insight],
    )
    result = InsightVerificationResult("p1", [make_field("p1", VerificationStatus.VERIFIED)])
    return generate_report([cluster], make_verification_report([result]), [post], "Google Gemini (gemini-flash-latest)")


def test_format_terminal_labels_speculative_fields():
    output = format_terminal(_sample_report())
    assert "Manual reconciliation is painful" in output
    assert "SPECULATIVE" in output
    assert "PROJECT HEALTH" in output
    assert "Google Gemini" in output


def test_format_markdown_has_proper_structure():
    output = format_markdown(_sample_report())
    assert output.startswith("# MarketRadar Insight Report")
    assert "## Executive Summary" in output
    assert "## Top Opportunities" in output
    assert "## Project Health" in output
    assert "> the evidence quote" in output  # verified quote rendered as blockquote
    assert "| Metric | Value |" in output  # health table


def test_save_markdown_file_writes_expected_content(tmp_path: Path):
    report = _sample_report()
    target = tmp_path / "subdir" / "report.md"

    result_path = save_markdown_file(report, target)

    assert result_path == target
    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert content.startswith("# MarketRadar Insight Report")
