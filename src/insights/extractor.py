"""The Extractor: turns one FetchedPost into one DiscussionInsight.

Never imports google.genai or any provider SDK directly — the only AI
access point is self._ai_provider.generate_text(), via the AIProvider
interface (src/ai/base.py). This keeps Task 3 provider-agnostic in
exactly the same way Task 2 kept the pipeline source-agnostic.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from src.ai import AIProvider, AIProviderError
from src.insights.models import (
    ConfidenceLevel,
    DiscussionInsight,
    PainPoint,
    Sentiment,
)
from src.insights.prompts import build_extraction_prompt
from src.models import FetchedPost

_MAX_ATTEMPTS = 2  # one retry if the model returns malformed/invalid JSON

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class InsightExtractionError(Exception):
    """Raised when a FetchedPost could not be turned into a valid,
    evidence-verified DiscussionInsight — because the AI call failed,
    its output wasn't valid/complete JSON, or its primary claim
    couldn't be verified against the source text.
    """


class Extractor:
    """Extracts one DiscussionInsight per FetchedPost, via any AIProvider."""

    def __init__(self, ai_provider: AIProvider) -> None:
        self._ai_provider = ai_provider

    def extract(self, post: FetchedPost) -> DiscussionInsight:
        """Analyze one post and return a validated DiscussionInsight.

        Raises:
            InsightExtractionError: If the AI call fails (after the
                provider's own transient-failure retries are
                exhausted), if the response can't be parsed as valid
                JSON after one retry, or if the primary pain point's
                evidence quote can't be verified against the post's
                own text.
        """
        source_text = _combined_source_text(post)
        prompt = build_extraction_prompt(post.title or "", post.text, post.url)

        last_error: Optional[Exception] = None
        for _ in range(_MAX_ATTEMPTS):
            try:
                raw_response = self._ai_provider.generate_text(prompt)
            except AIProviderError as exc:
                raise InsightExtractionError(f"AI provider call failed: {exc}") from exc

            try:
                data = _parse_json_response(raw_response)
                return _build_insight(data, post, source_text)
            except InsightExtractionError as exc:
                last_error = exc
                continue

        raise InsightExtractionError(
            f"Could not extract a valid insight after {_MAX_ATTEMPTS} attempts: {last_error}"
        )


def _combined_source_text(post: FetchedPost) -> str:
    return f"{post.title or ''}\n{post.text}"


def _parse_json_response(raw_response: str) -> Dict[str, Any]:
    cleaned = _FENCE_RE.sub("", raw_response.strip()).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise InsightExtractionError(
            f"AI response was not valid JSON: {exc}. "
            f"Raw response started with: {raw_response[:200]!r}"
        ) from exc


def _verified_quote(candidate: str, source_text: str) -> str:
    """Returns candidate if it's a verbatim substring of source_text,
    otherwise "" — dropping unverifiable quotes rather than propagating
    a possibly-fabricated one.

    This is the project's core non-fabrication guardrail, applied
    inline here for Task 3's own output. It is deliberately lightweight
    (exact substring match, nothing smarter) — the standalone Verifier
    (Task 4, not started) will do more thorough, cross-post checking
    later; this is just enough to keep Task 3 from ever presenting an
    invented quote.
    """
    if not candidate:
        return ""
    return candidate if candidate in source_text else ""


def _verified_quote_list(candidates: List[str], source_text: str) -> List[str]:
    return [q for q in (_verified_quote(c, source_text) for c in candidates) if q]


def _pain_point_from_data(data: Any, source_text: str) -> Optional[PainPoint]:
    if not isinstance(data, dict):
        return None
    description = str(data.get("description", "")).strip()
    quote = _verified_quote(str(data.get("evidence_quote", "")), source_text)
    if not description or not quote:
        return None
    return PainPoint(description=description, evidence_quote=quote)


def _confidence_from_value(value: Any) -> ConfidenceLevel:
    text = str(value).strip().lower()
    for level in ConfidenceLevel:
        if level.value.lower() == text:
            return level
    return ConfidenceLevel.WEAK  # unrecognized/missing -> the conservative default


def _sentiment_from_value(value: Any) -> Sentiment:
    text = str(value).strip().lower()
    for sentiment in Sentiment:
        if sentiment.value.lower() == text:
            return sentiment
    return Sentiment.NEUTRAL  # unrecognized/missing -> the conservative default


def _clamped_int(value: Any, low: int, high: int, default: int) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _build_insight(data: Dict[str, Any], post: FetchedPost, source_text: str) -> DiscussionInsight:
    primary = _pain_point_from_data(data.get("primary_pain_point"), source_text)
    if primary is None:
        raise InsightExtractionError(
            "Primary pain point missing, empty, or its evidence_quote could not be "
            "verified against the source text - refusing to present an unverified "
            "primary claim."
        )

    secondary_raw = data.get("secondary_pain_points") or []
    secondary = (
        [pp for pp in (_pain_point_from_data(item, source_text) for item in secondary_raw) if pp]
        if isinstance(secondary_raw, list)
        else []
    )

    raw_buying_signals = data.get("buying_signals") or []
    raw_supporting_evidence = data.get("supporting_evidence") or []

    return DiscussionInsight(
        source_post_id=post.id,
        source_url=post.url,
        is_mock_source=post.is_mock,
        primary_pain_point=primary,
        secondary_pain_points=secondary,
        user_persona=str(data.get("user_persona", "")).strip(),
        feature_requests=_string_list(data.get("feature_requests")),
        buying_signals=_verified_quote_list(_string_list(raw_buying_signals), source_text),
        emotional_sentiment=_sentiment_from_value(data.get("emotional_sentiment")),
        urgency_score=_clamped_int(data.get("urgency_score"), 1, 10, default=1),
        opportunity_score=_clamped_int(data.get("opportunity_score"), 1, 100, default=1),
        confidence=_confidence_from_value(data.get("confidence")),
        startup_opportunity=str(data.get("startup_opportunity", "")).strip(),
        supporting_evidence=_verified_quote_list(_string_list(raw_supporting_evidence), source_text),
    )
