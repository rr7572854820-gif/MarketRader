"""Typed data model for the Insight Report Generator.

Reuses ConfidenceLevel from src/insights/models.py rather than
redefining it. Nothing here does any computation — see
report_generator.py for how these get built, and formatter.py for how
they get rendered. This file is just shapes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List

from src.insights.models import ConfidenceLevel


@dataclass(frozen=True)
class OpportunityReportEntry:
    """One opportunity cluster, formatted for the report.

    Attributes:
        title: The cluster's canonical pain-point label.
        opportunity_score: Average across the cluster's insights.
            SPECULATIVE — an AI-generated inference, not a verified
            finding (see src/insights/models.py). Every renderer must
            label it as such; never print this bare.
        confidence: The cluster's aggregate ConfidenceLevel — real,
            not speculative (reflects how directly the evidence was
            stated, per the project's existing taxonomy).
        frequency: How many independent discussions back this cluster.
        verification_rate: Fraction (0.0-1.0) of this cluster's claims
            that were independently Verified (see src/verification/).
            0.0 with no underlying claims means "no verification data
            available," not "verification failed" — callers must
            check has_verification_data before implying failure.
        has_verification_data: False if no VerificationReport results
            were found for this cluster's discussions at all.
        supporting_quotes: Verbatim quotes, but ONLY ones the Verifier
            actually marked Verified — this report never surfaces a
            raw AI-extracted quote that verification didn't confirm,
            not even loosely-matched Partial-status sentences.
        representative_discussions: Source URLs for this cluster,
            capped to a small readable number.
        suggested_customer_segment: One representative user_persona
            from the cluster. SPECULATIVE, same reasoning as
            opportunity_score — never a synthesized/merged persona,
            since that would risk fabricating a composite that no
            single discussion actually supports.
        recommended_next_action: A deterministic, rule-based research
            suggestion (read more, verify manually, wait for
            recurrence, follow up directly) — never a build/invest
            verdict. See report_generator.py's docstring for why.
    """

    title: str
    opportunity_score: float
    confidence: ConfidenceLevel
    frequency: int
    verification_rate: float
    has_verification_data: bool
    supporting_quotes: List[str]
    representative_discussions: List[str]
    suggested_customer_segment: str
    recommended_next_action: str


@dataclass(frozen=True)
class ProjectHealthSummary:
    """Overall run statistics, not tied to any one opportunity."""

    total_discussions_fetched: int
    total_discussions_analyzed: int
    total_opportunity_clusters: int
    total_verified_insights: int
    verification_percentage: float
    ai_provider_used: str
    analysis_timestamp: datetime


@dataclass(frozen=True)
class InsightReport:
    """The complete report: an executive summary, ranked opportunities,
    and overall project health — everything a formatter needs to
    render either terminal or Markdown output. All three fields are
    required; an InsightReport with no opportunities is represented by
    an empty top_opportunities list, not a missing one.
    """

    executive_summary: str
    top_opportunities: List[OpportunityReportEntry]
    project_health: ProjectHealthSummary
