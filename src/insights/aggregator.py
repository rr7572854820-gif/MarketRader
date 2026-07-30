"""Aggregates multiple DiscussionInsights into ranked OpportunityClusters:
merges duplicate pain points, clusters similar discussions, counts
occurrences, and ranks the result.

Task 3.1 history: the original implementation clustered on keyword
(Jaccard) overlap between pain point descriptions. Measured against the
mock dataset's two deliberate duplicate pairs, it merged neither — 7
discussions produced 7 clusters, with similarity scores an order of
magnitude below the merge threshold (see SESSION.md for the numbers).
Root cause: the AI generates an independent one-sentence paraphrase per
discussion, and two paraphrases of the same real problem often share
almost no literal vocabulary even when a human instantly recognizes
them as the same issue — this is a semantic-similarity problem, and
keyword overlap has no access to semantics.

Fix: clustering is now AI-assisted by default (one batched
generate_text call covering all discussions at once, via AIProvider —
never a direct Gemini import, same rule as everywhere else in this
project), with the original keyword-overlap heuristic kept only as a
deterministic fallback for when no AI provider is available or the AI
call/response fails. This is deliberately still not real semantic
clustering research (no embeddings, no formal similarity metric) — it
delegates the judgment call to the same model already doing extraction,
which has actually demonstrated it can tell "Stripe/QuickBooks
reconciliation" and "paying a bookkeeper to do reconciliation" are the
same problem, which no amount of keyword tuning could.
"""

from __future__ import annotations

import json
import re
from typing import List, Optional, Set

from src.ai import AIProvider, AIProviderError
from src.insights.models import ConfidenceLevel, DiscussionInsight, OpportunityCluster
from src.insights.prompts import build_clustering_prompt

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for",
    "with", "is", "are", "was", "were", "it", "its", "this", "that",
    "my", "i", "me", "so", "just", "every", "each", "at", "as", "by",
    "be", "not", "than", "then", "if", "any", "all", "have", "has",
}
_LEXICAL_SIMILARITY_THRESHOLD = 0.35

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class ClusteringError(Exception):
    """Raised internally when the AI's clustering response has no
    usable structure at all. Caught by Aggregator.aggregate(), which
    falls back to lexical clustering rather than propagating this —
    a clustering failure should degrade cluster quality, not crash
    the whole analysis run.
    """


class Aggregator:
    """Merges duplicate pain points, clusters similar discussions,
    counts occurrences, and ranks the result by opportunity score.

    Args:
        ai_provider: If given, used for AI-assisted semantic
            clustering (the default, and the only mode that has been
            measured to actually merge duplicates — see module
            docstring). If None, or if the AI call/response fails,
            falls back to deterministic keyword-overlap clustering.
    """

    def __init__(self, ai_provider: Optional[AIProvider] = None) -> None:
        self._ai_provider = ai_provider
        # Set by aggregate(); callers (e.g. the CLI) should check these
        # and tell the user which clustering path actually ran, rather
        # than a fallback happening silently — that was a real gap,
        # found by hitting a Gemini quota limit mid-testing.
        self.last_method: str = "none"  # "ai" or "lexical_fallback"
        self.last_fallback_reason: Optional[str] = None

    def aggregate(self, insights: List[DiscussionInsight]) -> List[OpportunityCluster]:
        if not insights:
            return []

        groups = self._cluster_indices(insights)
        result = [self._finalize([insights[i] for i in group]) for group in groups]
        result.sort(key=lambda c: (c.average_opportunity_score, c.occurrence_count), reverse=True)
        return result

    def _cluster_indices(self, insights: List[DiscussionInsight]) -> List[List[int]]:
        # last_method / last_fallback_reason are set here rather than
        # printed here — Aggregator is business logic, and nothing else
        # in this codebase prints from that layer (Extractor raises,
        # the CLI prints). A previous version of this fix printed
        # directly from here; fixed to stay consistent and testable.
        if self._ai_provider is not None:
            try:
                groups = self._ai_cluster(insights)
                self.last_method = "ai"
                self.last_fallback_reason = None
                return groups
            except (AIProviderError, ClusteringError) as exc:
                # A silent fallback here would hide exactly the kind of
                # failure (e.g. quota exhaustion) that makes clustering
                # quality look like a code bug when it's actually an API
                # limit — this was a real gap, found by hitting it.
                self.last_fallback_reason = f"{type(exc).__name__}: {exc}"
        self.last_method = "lexical_fallback"
        return self._lexical_cluster(insights)

    def _ai_cluster(self, insights: List[DiscussionInsight]) -> List[List[int]]:
        assert self._ai_provider is not None
        items = [(i.primary_pain_point.description, i.primary_pain_point.evidence_quote) for i in insights]
        prompt = build_clustering_prompt(items)
        raw_response = self._ai_provider.generate_text(prompt)
        return _parse_clustering_response(raw_response, len(insights))

    def _lexical_cluster(self, insights: List[DiscussionInsight]) -> List[List[int]]:
        groups: List[List[int]] = []
        group_keywords: List[Set[str]] = []

        for idx, insight in enumerate(insights):
            keywords = _insight_keywords(insight)
            best_group = -1
            best_score = 0.0
            for g, existing_keywords in enumerate(group_keywords):
                score = _jaccard_similarity(keywords, existing_keywords)
                if score > best_score:
                    best_score = score
                    best_group = g

            if best_group >= 0 and best_score >= _LEXICAL_SIMILARITY_THRESHOLD:
                groups[best_group].append(idx)
                group_keywords[best_group] |= keywords
            else:
                groups.append([idx])
                group_keywords.append(keywords)

        return groups

    def _finalize(self, insights: List[DiscussionInsight]) -> OpportunityCluster:
        occurrence_count = len(insights)
        return OpportunityCluster(
            label=insights[0].primary_pain_point.description,
            occurrence_count=occurrence_count,
            average_opportunity_score=round(
                sum(i.opportunity_score for i in insights) / occurrence_count, 1
            ),
            average_urgency_score=round(
                sum(i.urgency_score for i in insights) / occurrence_count, 1
            ),
            confidence=_aggregate_confidence(insights),
            insights=insights,
        )


def _parse_clustering_response(raw_response: str, n: int) -> List[List[int]]:
    """Parses and validates the AI's clustering response into a list of
    index-groups, guaranteeing every index in range(n) appears in
    exactly one group regardless of imperfections in the AI's output:
    duplicate indices are deduped (first occurrence wins), out-of-range
    or malformed entries are dropped, and any index the AI never
    mentioned becomes its own singleton group. This means a partially
    malformed AI response degrades gracefully instead of triggering a
    full fallback to lexical clustering — only a response with no
    usable "clusters" structure at all does that.

    Raises:
        ClusteringError: If the response isn't valid JSON, or has no
            usable "clusters" list at all.
    """
    cleaned = _FENCE_RE.sub("", raw_response.strip()).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ClusteringError(f"AI clustering response was not valid JSON: {exc}") from exc

    raw_clusters = data.get("clusters") if isinstance(data, dict) else None
    if not isinstance(raw_clusters, list) or not raw_clusters:
        raise ClusteringError("AI clustering response had no usable 'clusters' list.")

    seen: Set[int] = set()
    groups: List[List[int]] = []
    for entry in raw_clusters:
        if not isinstance(entry, dict):
            continue
        indices = entry.get("member_indices")
        if not isinstance(indices, list):
            continue
        group = [idx for idx in indices if _is_new_valid_index(idx, n, seen)]
        for idx in group:
            seen.add(idx)
        if group:
            groups.append(group)

    for idx in range(n):
        if idx not in seen:
            groups.append([idx])

    return groups


def _is_new_valid_index(idx: object, n: int, seen: Set[int]) -> bool:
    return isinstance(idx, int) and 0 <= idx < n and idx not in seen


def _keywords(text: str) -> Set[str]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _insight_keywords(insight: DiscussionInsight) -> Set[str]:
    """Keyword set used only by the deterministic fallback clusterer —
    see module docstring for why this alone is known to be insufficient
    for real semantic duplicates. Pulls from more than just the primary
    description (secondary pain points, evidence quotes) for a wider,
    still-cheap signal.
    """
    text_parts = [insight.primary_pain_point.description, insight.primary_pain_point.evidence_quote]
    for pp in insight.secondary_pain_points:
        text_parts.append(pp.description)
        text_parts.append(pp.evidence_quote)
    text_parts.extend(insight.supporting_evidence)
    return _keywords(" ".join(text_parts))


def _jaccard_similarity(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


def _aggregate_confidence(insights: List[DiscussionInsight]) -> ConfidenceLevel:
    """Corroboration is meaningful: independent discussions backing the
    same cluster shouldn't score lower confidence than any one of them
    alone. Takes the strongest individual confidence present; if none
    hit Strong but more than one discussion corroborates the cluster,
    treats that as Moderate rather than leaving it at a single weak
    discussion's Weak rating.
    """
    levels = [i.confidence for i in insights]
    if ConfidenceLevel.STRONG in levels:
        return ConfidenceLevel.STRONG
    if ConfidenceLevel.MODERATE in levels or len(insights) > 1:
        return ConfidenceLevel.MODERATE
    return ConfidenceLevel.WEAK
