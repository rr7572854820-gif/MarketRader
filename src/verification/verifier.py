"""The Verification Engine: independently re-checks every claim in a
DiscussionInsight against its original source discussion.

Deliberately zero AI calls, and deliberately independent from
src/insights/extractor.py — it imports only shared data types
(DiscussionInsight, FetchedPost, ConfidenceLevel), never extraction
logic. Checking an AI's claim against real, immutable source text is a
meaningful anti-hallucination signal; checking it with a second AI call
is not — it just risks one model rubber-stamping the other's mistake.
Every check here is plain string matching, testable with zero API cost
and zero network dependency (see the test suite).

Two different kinds of claims get two different, honestly-labeled
verification ceilings:
  - Quote-bearing claims (primary/secondary pain points, supporting
    evidence, buying signals) were already required by the Extractor
    to be verbatim substrings of the source. Re-confirming that here
    is real defense-in-depth: it catches a regression in the
    Extractor's own check, a version mismatch between the insight and
    the post it's verified against, or any other way the two could
    have drifted apart. These can reach VERIFIED.
  - Claims with no attached quote at all (user_persona,
    feature_requests) were never evidence claims to begin with — they
    are the AI's inference (see src/insights/models.py). These can
    reach at most PARTIAL, based on keyword-level textual grounding in
    the source, never VERIFIED — there is no verbatim quote to
    confirm, so claiming VERIFIED status for them would itself be a
    form of overclaiming confidence this project exists to avoid.
"""

from __future__ import annotations

import re
from typing import List, Set

from src.insights.models import ConfidenceLevel, DiscussionInsight
from src.models import FetchedPost
from src.verification.models import (
    FieldVerification,
    InsightVerificationResult,
    VerificationReport,
    VerificationStatus,
)

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for",
    "with", "is", "are", "was", "were", "it", "its", "this", "that",
    "my", "i", "me", "so", "just", "every", "each", "at", "as", "by",
    "be", "not", "than", "then", "if", "any", "all", "have", "has",
}
_PARTIAL_KEYWORD_OVERLAP_RATIO = 0.3  # fraction of the claim's own keywords that must appear in a source sentence


class VerificationError(Exception):
    """Raised when a DiscussionInsight is verified against a FetchedPost
    it doesn't actually belong to (source_post_id mismatch). Verifying
    a claim against the wrong source is worse than not verifying it at
    all — it could make a hallucinated claim look "confirmed" purely by
    textual coincidence with unrelated content.
    """


class Verifier:
    """Independently re-verifies every claim in a DiscussionInsight
    against its own original FetchedPost.
    """

    def verify(self, insight: DiscussionInsight, source_post: FetchedPost) -> InsightVerificationResult:
        """Verify one insight against its own source post.

        Raises:
            VerificationError: If insight.source_post_id doesn't match
                source_post.id.
        """
        if insight.source_post_id != source_post.id:
            raise VerificationError(
                f"Insight claims source_post_id={insight.source_post_id!r} but was given "
                f"source_post.id={source_post.id!r} - refusing to verify a claim against "
                f"the wrong source."
            )

        source_text = _combined_source_text(source_post)
        checks: List[FieldVerification] = []

        checks.append(
            self._verify_quote_claim(
                "primary_pain_point",
                insight.primary_pain_point.description,
                insight.primary_pain_point.evidence_quote,
                source_text,
                source_post.id,
            )
        )
        for i, pp in enumerate(insight.secondary_pain_points):
            checks.append(
                self._verify_quote_claim(
                    f"secondary_pain_point[{i}]", pp.description, pp.evidence_quote, source_text, source_post.id
                )
            )
        for i, quote in enumerate(insight.supporting_evidence):
            checks.append(self._verify_bare_quote(f"supporting_evidence[{i}]", quote, source_text, source_post.id))
        for i, quote in enumerate(insight.buying_signals):
            checks.append(self._verify_bare_quote(f"buying_signal[{i}]", quote, source_text, source_post.id))

        checks.append(
            self._verify_speculative_claim("user_persona", insight.user_persona, source_text, source_post.id)
        )
        for i, fr in enumerate(insight.feature_requests):
            checks.append(self._verify_speculative_claim(f"feature_request[{i}]", fr, source_text, source_post.id))

        return InsightVerificationResult(source_post_id=source_post.id, field_verifications=checks)

    def verify_all(self, insights: List[DiscussionInsight], posts: List[FetchedPost]) -> VerificationReport:
        """Verify every insight against its matching post from `posts`.

        Never silently discards an insight it can't verify: if an
        insight's source post isn't found in `posts`, every field is
        reported as Unverified with that reason, rather than the
        insight being dropped from the report.
        """
        posts_by_id = {p.id: p for p in posts}
        results: List[InsightVerificationResult] = []

        for insight in insights:
            post = posts_by_id.get(insight.source_post_id)
            if post is None:
                results.append(_missing_source_result(insight))
                continue
            results.append(self.verify(insight, post))

        return _build_report(results)

    def _verify_quote_claim(
        self, field_name: str, claim_text: str, quote: str, source_text: str, source_id: str
    ) -> FieldVerification:
        if not claim_text or not quote:
            return _unverified(field_name, claim_text or "", source_id)
        if quote in source_text:
            return FieldVerification(
                field_name=field_name,
                claim_text=claim_text,
                verification_status=VerificationStatus.VERIFIED,
                confidence=ConfidenceLevel.STRONG,
                supporting_quotes=[quote],
                source_discussion_ids=[source_id],
            )
        return _unverified(field_name, claim_text, source_id)

    def _verify_bare_quote(self, field_name: str, quote: str, source_text: str, source_id: str) -> FieldVerification:
        if not quote:
            return _unverified(field_name, "", source_id)
        if quote in source_text:
            return FieldVerification(
                field_name=field_name,
                claim_text=quote,
                verification_status=VerificationStatus.VERIFIED,
                confidence=ConfidenceLevel.STRONG,
                supporting_quotes=[quote],
                source_discussion_ids=[source_id],
            )
        return _unverified(field_name, quote, source_id)

    def _verify_speculative_claim(
        self, field_name: str, claim_text: str, source_text: str, source_id: str
    ) -> FieldVerification:
        if not claim_text:
            return _unverified(field_name, "", source_id)
        matches = _find_supporting_sentences(claim_text, source_text)
        if matches:
            return FieldVerification(
                field_name=field_name,
                claim_text=claim_text,
                verification_status=VerificationStatus.PARTIAL,
                confidence=ConfidenceLevel.MODERATE,
                supporting_quotes=matches,
                source_discussion_ids=[source_id],
            )
        return _unverified(field_name, claim_text, source_id)


def _unverified(field_name: str, claim_text: str, source_id: str) -> FieldVerification:
    return FieldVerification(
        field_name=field_name,
        claim_text=claim_text,
        verification_status=VerificationStatus.UNVERIFIED,
        confidence=ConfidenceLevel.WEAK,
        supporting_quotes=[],
        source_discussion_ids=[source_id],
    )


def _missing_source_result(insight: DiscussionInsight) -> InsightVerificationResult:
    """Used only when the insight's own source post wasn't provided to
    verify_all() at all — every field is explicitly Unverified rather
    than the insight being silently skipped, per "never silently
    discard failures."
    """
    field_names = (
        ["primary_pain_point"]
        + [f"secondary_pain_point[{i}]" for i in range(len(insight.secondary_pain_points))]
        + [f"supporting_evidence[{i}]" for i in range(len(insight.supporting_evidence))]
        + [f"buying_signal[{i}]" for i in range(len(insight.buying_signals))]
        + ["user_persona"]
        + [f"feature_request[{i}]" for i in range(len(insight.feature_requests))]
    )
    return InsightVerificationResult(
        source_post_id=insight.source_post_id,
        field_verifications=[
            _unverified(name, "source post not provided to verifier", insight.source_post_id) for name in field_names
        ],
    )


def _combined_source_text(post: FetchedPost) -> str:
    return f"{post.title or ''}\n{post.text}"


def _keywords(text: str) -> Set[str]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _find_supporting_sentences(claim_text: str, source_text: str) -> List[str]:
    """Deterministic, keyword-overlap heuristic for claims with no
    attached quote. Returns source sentences sharing at least
    _PARTIAL_KEYWORD_OVERLAP_RATIO of the claim's significant keywords
    — a plausibility signal, never a proof of the claim, and callers
    must never present these as verbatim confirmation (see module
    docstring).
    """
    claim_keywords = _keywords(claim_text)
    if not claim_keywords:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", source_text)
    matches = []
    for raw_sentence in sentences:
        sentence = raw_sentence.strip()
        if not sentence:
            continue
        overlap = claim_keywords & _keywords(sentence)
        if overlap and len(overlap) / len(claim_keywords) >= _PARTIAL_KEYWORD_OVERLAP_RATIO:
            matches.append(sentence)
    return matches


def _build_report(results: List[InsightVerificationResult]) -> VerificationReport:
    all_fields = [fv for r in results for fv in r.field_verifications]
    total = len(all_fields)
    verified = sum(1 for fv in all_fields if fv.verification_status == VerificationStatus.VERIFIED)
    partial = sum(1 for fv in all_fields if fv.verification_status == VerificationStatus.PARTIAL)
    unverified = sum(1 for fv in all_fields if fv.verification_status == VerificationStatus.UNVERIFIED)
    rate = round(verified / total, 3) if total else 0.0
    return VerificationReport(
        total_claims=total,
        verified_count=verified,
        partial_count=partial,
        unverified_count=unverified,
        verification_rate=rate,
        results=results,
    )
