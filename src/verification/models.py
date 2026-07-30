"""Typed output shapes for the Verification Engine.

Reuses DiscussionInsight/FetchedPost (src/insights/models.py,
src/models.py) and ConfidenceLevel (src/insights/models.py) rather than
redefining them — per Task 4's "reuse existing models where
appropriate." VerificationStatus is new: it's a different axis than
ConfidenceLevel (which describes how directly the *original* AI claim
was stated; VerificationStatus describes whether *this independent
check* actually found the evidence for it).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List

from src.insights.models import ConfidenceLevel


class VerificationStatus(str, Enum):
    """Verified: an exact, verbatim quote was found in the source text.
    Partial: no exact quote applies (the field was never a quote claim
        to begin with — e.g. user_persona, feature_requests) but some
        keyword-level textual grounding was found in the source.
    Unverified: no supporting evidence was found at all. This is the
        required outcome, not an error, when evidence genuinely isn't
        there — see module docstring on "never fabricate evidence."
    """

    VERIFIED = "Verified"
    PARTIAL = "Partial"
    UNVERIFIED = "Unverified"


@dataclass(frozen=True)
class FieldVerification:
    """The verification result for one single claim (one pain point,
    one quote, the persona, one feature request, ...).

    Attributes:
        field_name: Which field/item this is, e.g. "primary_pain_point",
            "secondary_pain_point[1]", "feature_request[0]".
        claim_text: The actual claim text being checked.
        verification_status: See VerificationStatus.
        confidence: Reuses the project's existing 3-tier taxonomy.
            Deterministically derived from verification_status (Strong
            for Verified, Moderate for Partial, Weak for Unverified) —
            not a second, independent judgment call.
        supporting_quotes: Verbatim text found in the source that
            backs this claim. For Verified fields, this IS the claim's
            own evidence quote, re-confirmed independently. For Partial
            fields, these are source sentences with keyword overlap —
            plausible support, not a proven verbatim match, and must
            never be presented as though it were one. Empty for
            Unverified fields.
        source_discussion_ids: Which FetchedPost(s) this claim was
            checked against.
    """

    field_name: str
    claim_text: str
    verification_status: VerificationStatus
    confidence: ConfidenceLevel
    supporting_quotes: List[str]
    source_discussion_ids: List[str]


@dataclass(frozen=True)
class InsightVerificationResult:
    """All field-level verification results for one DiscussionInsight."""

    source_post_id: str
    field_verifications: List[FieldVerification] = field(default_factory=list)

    @property
    def overall_status(self) -> VerificationStatus:
        """Worst-case rollup: Unverified if any field is Unverified,
        else Partial if any field is Partial, else Verified. Chosen
        deliberately pessimistic — a single unverified claim should not
        be hidden behind an average of mostly-fine ones.
        """
        statuses = {fv.verification_status for fv in self.field_verifications}
        if VerificationStatus.UNVERIFIED in statuses:
            return VerificationStatus.UNVERIFIED
        if VerificationStatus.PARTIAL in statuses:
            return VerificationStatus.PARTIAL
        return VerificationStatus.VERIFIED


@dataclass(frozen=True)
class VerificationReport:
    """Aggregate verification statistics across all checked insights.

    verification_rate is strictly verified_count / total_claims —
    Partial claims are deliberately NOT counted as verified, even
    fractionally, so this number can't be inflated by claims that only
    found loose keyword support.
    """

    total_claims: int
    verified_count: int
    partial_count: int
    unverified_count: int
    verification_rate: float
    results: List[InsightVerificationResult]
