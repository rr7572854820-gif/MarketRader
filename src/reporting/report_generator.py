"""Builds an InsightReport from already-computed pipeline output.

Architecture: no AI calls, and this module never touches
src/insights/ or src/verification/ logic — it only reads their output
types (OpportunityCluster, VerificationReport, DiscussionInsight,
FetchedPost). Every number here is either a direct pass-through of an
existing value or a deterministic aggregation of one — nothing is
generated, guessed, or templated from AI.

On "Recommended Next Action": every recommendation produced here is a
*research* action (read the source, verify manually, wait for
recurrence, follow up directly with the people who described the
problem) — never a build/invest/viability verdict. PRD.md §7's
non-goals are explicit that MarketRadar "does not make investment,
funding, or go/no-go decisions on behalf of the user" and that
"MarketRadar's job ends at presenting well-reasoned, well-sourced
findings" (§10). A report generator is exactly the kind of place that
temptation could quietly creep in disguised as being "more useful" —
resisted deliberately here; see _recommend_next_action.

On "Supporting Quotes": pulled only from FieldVerification entries the
Verifier actually marked VERIFIED — never straight from
DiscussionInsight's raw fields, and never from Partial-status
loosely-matched sentences. Using the Verifier's output downstream,
rather than just running it alongside the report, is the entire point
of having built Task 4 first.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Set

from src.insights.models import ConfidenceLevel, OpportunityCluster
from src.models import FetchedPost
from src.reporting.models import InsightReport, OpportunityReportEntry, ProjectHealthSummary
from src.verification.models import InsightVerificationResult, VerificationReport, VerificationStatus

_MAX_SUPPORTING_QUOTES = 5
_MAX_REPRESENTATIVE_DISCUSSIONS = 5


def generate_report(
    clusters: List[OpportunityCluster],
    verification_report: VerificationReport,
    posts: List[FetchedPost],
    ai_provider_used: str,
) -> InsightReport:
    """Build a complete InsightReport.

    Args:
        clusters: Ranked opportunity clusters (already sorted by the
            Aggregator — this function preserves that order).
        verification_report: The Verifier's output for the same run.
        posts: The original fetched discussions, used only for the
            total-fetched count in project health (some may have
            failed extraction and therefore have no insight/cluster).
        ai_provider_used: A human-readable label for which AI backend
            produced the underlying insights (e.g. "Google Gemini
            (gemini-flash-latest)" or "Mock AI provider") — passed in
            rather than re-derived, since this module has no business
            inspecting AIProvider internals.
    """
    results_by_post_id: Dict[str, InsightVerificationResult] = {r.source_post_id: r for r in verification_report.results}

    opportunities = [_build_entry(cluster, results_by_post_id) for cluster in clusters]

    all_insight_ids = {insight.source_post_id for cluster in clusters for insight in cluster.insights}
    verified_insight_count = sum(
        1
        for post_id in all_insight_ids
        if post_id in results_by_post_id and results_by_post_id[post_id].overall_status == VerificationStatus.VERIFIED
    )

    health = ProjectHealthSummary(
        total_discussions_fetched=len(posts),
        total_discussions_analyzed=len(all_insight_ids),
        total_opportunity_clusters=len(clusters),
        total_verified_insights=verified_insight_count,
        verification_percentage=verification_report.verification_rate * 100,
        ai_provider_used=ai_provider_used,
        analysis_timestamp=datetime.now(timezone.utc),
    )

    summary = _build_executive_summary(opportunities, health)

    return InsightReport(executive_summary=summary, top_opportunities=opportunities, project_health=health)


def _build_entry(
    cluster: OpportunityCluster, results_by_post_id: Dict[str, InsightVerificationResult]
) -> OpportunityReportEntry:
    post_ids = [insight.source_post_id for insight in cluster.insights]
    cluster_results = [results_by_post_id[pid] for pid in post_ids if pid in results_by_post_id]
    all_fields = [fv for result in cluster_results for fv in result.field_verifications]

    has_verification_data = bool(all_fields)
    verification_rate = (
        sum(1 for fv in all_fields if fv.verification_status == VerificationStatus.VERIFIED) / len(all_fields)
        if all_fields
        else 0.0
    )

    supporting_quotes = _collect_verified_quotes(all_fields)
    representative_discussions = [insight.source_url for insight in cluster.insights][:_MAX_REPRESENTATIVE_DISCUSSIONS]
    segment = _pick_customer_segment(cluster)
    next_action = _recommend_next_action(cluster.confidence, verification_rate, has_verification_data, cluster.occurrence_count)

    return OpportunityReportEntry(
        title=cluster.label,
        opportunity_score=cluster.average_opportunity_score,
        confidence=cluster.confidence,
        frequency=cluster.occurrence_count,
        verification_rate=round(verification_rate, 3),
        has_verification_data=has_verification_data,
        supporting_quotes=supporting_quotes,
        representative_discussions=representative_discussions,
        suggested_customer_segment=segment,
        recommended_next_action=next_action,
    )


def _collect_verified_quotes(all_fields) -> List[str]:
    seen: Set[str] = set()
    quotes: List[str] = []
    for fv in all_fields:
        if fv.verification_status != VerificationStatus.VERIFIED:
            continue
        for quote in fv.supporting_quotes:
            if quote not in seen:
                seen.add(quote)
                quotes.append(quote)
    return quotes[:_MAX_SUPPORTING_QUOTES]


def _pick_customer_segment(cluster: OpportunityCluster) -> str:
    """Returns one representative, unmodified user_persona from the
    cluster — deliberately not a synthesized/merged persona across
    multiple insights, since blending several AI-generated personas
    into one composite would itself be a small act of fabrication with
    no single discussion actually backing the merged result.
    """
    for insight in cluster.insights:
        if insight.user_persona:
            return insight.user_persona
    return "Not specified - no persona was inferred for any discussion in this cluster."


def _recommend_next_action(
    confidence: ConfidenceLevel, verification_rate: float, has_verification_data: bool, frequency: int
) -> str:
    """Deterministic, rule-based - see module docstring for why this
    never recommends a build/invest decision.
    """
    if not has_verification_data:
        return "No verification data available for this cluster - read the original discussions directly before drawing any conclusion."
    if verification_rate < 0.5:
        return (
            "Low verification rate - before treating this as a real signal, manually re-read the "
            "original discussions and confirm the claims yourself."
        )
    if frequency == 1:
        return "Only one discussion found so far - monitor for recurrence before investing more research time here."
    if confidence == ConfidenceLevel.STRONG and verification_rate >= 0.8:
        return (
            "Well-corroborated and independently verified - a reasonable next step is reading the full "
            "original discussions and, if still compelling, reaching out directly to the people who "
            "described this problem."
        )
    return "Moderate signal - worth a closer manual read of the original discussions before deciding whether to dig further."


def _build_executive_summary(opportunities: List[OpportunityReportEntry], health: ProjectHealthSummary) -> str:
    if not opportunities:
        return (
            f"Analyzed {health.total_discussions_analyzed} discussion(s) from "
            f"{health.total_discussions_fetched} fetched; no opportunity clusters were produced. "
            f"{health.verification_percentage:.1f}% of underlying claims were independently verified."
        )

    top = opportunities[0]
    return (
        f"This report summarizes {health.total_discussions_analyzed} discussion(s) analyzed "
        f"(of {health.total_discussions_fetched} fetched), grouped into "
        f"{health.total_opportunity_clusters} distinct opportunity area(s) after deduplication. "
        f"{health.verification_percentage:.1f}% of the underlying claims were independently verified "
        f"against their original source text using {health.ai_provider_used}.\n\n"
        f'The top-ranked opportunity, "{top.title}," was identified from {top.frequency} independent '
        f"discussion(s) with {top.confidence.value} confidence and a {top.verification_rate:.0%} "
        f"verification rate.\n\n"
        f"All opportunity scores and customer segment suggestions in this report are AI-generated "
        f"inferences from a small sample of public discussions - they are directional signals for "
        f"further research, not validated business conclusions. See each opportunity's Recommended "
        f"Next Action for a suggested follow-up step."
    )
