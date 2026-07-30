"""Strongly-typed data model for the AI Insight Engine's output.

Every field here is either:

(a) directly evidence-backed — must be a verbatim, verified quote from
    the source discussion (PainPoint.evidence_quote, supporting_evidence,
    buying_signals), checked against the source text by the Extractor
    before a DiscussionInsight is ever constructed; or

(b) explicitly speculative inference (user_persona, startup_opportunity,
    opportunity_score, urgency_score, emotional_sentiment) — the AI's
    extrapolation from limited evidence, not an observed fact.

Category (b), in particular opportunity_score and startup_opportunity,
sits directly against this project's stated non-goal of generating
startup ideas or scoring market attractiveness prematurely (see
README.md, PRD.md §7/§10, ROADMAP.md Phase 5 Milestone 5.3). These
fields exist here because the user explicitly requested them for their
own personal tool — but every consumer of this data (the aggregator,
the CLI report) must keep them visibly labeled as low-confidence,
single-source speculation, never presented as a verified finding.
Do not add a code path that surfaces opportunity_score or
startup_opportunity without that label attached.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List


class ConfidenceLevel(str, Enum):
    """Matches the project's existing lightweight 3-tier evidence
    taxonomy (see SESSION.md / ROADMAP.md Milestone 0.3) rather than
    inventing a new scale for this task alone.
    """

    STRONG = "Strong"
    MODERATE = "Moderate"
    WEAK = "Weak"


class Sentiment(str, Enum):
    """A constrained vocabulary rather than free text, so downstream
    code can rely on a fixed set of values instead of parsing
    arbitrary strings.
    """

    FRUSTRATED = "Frustrated"
    ANGRY = "Angry"
    ANXIOUS = "Anxious"
    CONFUSED = "Confused"
    NEUTRAL = "Neutral"
    HOPEFUL = "Hopeful"
    SATISFIED = "Satisfied"
    EXCITED = "Excited"


@dataclass(frozen=True)
class PainPoint:
    """A single pain point.

    evidence_quote must be a verbatim, verified substring of its
    source post's text — the Extractor guarantees this before
    construction, never a paraphrase or invented quote.
    """

    description: str
    evidence_quote: str


@dataclass(frozen=True)
class DiscussionInsight:
    """Structured analysis of one discussion (one FetchedPost).

    See module docstring for the evidence-vs-inference distinction
    between fields — it is not cosmetic, it is the project's core
    integrity guarantee applied to this specific output shape.
    """

    source_post_id: str
    source_url: str
    is_mock_source: bool

    primary_pain_point: PainPoint
    secondary_pain_points: List[PainPoint]

    user_persona: str  # SPECULATIVE — see module docstring
    feature_requests: List[str]
    buying_signals: List[str]  # verbatim quotes only, verified; may be empty

    emotional_sentiment: Sentiment
    urgency_score: int  # 1-10, SPECULATIVE
    opportunity_score: int  # 1-100, SPECULATIVE — see module docstring
    confidence: ConfidenceLevel
    startup_opportunity: str  # SPECULATIVE — see module docstring

    supporting_evidence: List[str]  # verbatim quotes only, verified


@dataclass(frozen=True)
class OpportunityCluster:
    """A group of DiscussionInsights whose primary pain points were
    judged similar enough to merge.

    Produced by a simple, deterministic keyword-overlap heuristic (see
    src/insights/aggregator.py) — not NLP-grade semantic clustering.
    Real cross-source deduplication is scoped as its own, harder,
    later-phase effort in ROADMAP.md (Milestone 3.2); this is meant to
    avoid obvious duplicate counting on a single-source personal MVP,
    not to solve that problem generally.
    """

    label: str
    occurrence_count: int
    average_opportunity_score: float  # SPECULATIVE — see module docstring
    average_urgency_score: float  # SPECULATIVE
    confidence: ConfidenceLevel
    insights: List[DiscussionInsight]
