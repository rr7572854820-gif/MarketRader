"""Prompt templates for the AI Insight Engine.

Kept separate from parsing/validation/business logic
(src/insights/extractor.py) so prompt wording can be iterated on
without touching the code that consumes the result. Nothing in this
module calls an AI provider — it only builds prompt strings.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

CLUSTERING_INSTRUCTIONS = """You are grouping business pain-point discussions by their underlying real-world problem, not by wording. Two discussions that describe the same underlying problem in different words (different specific tools, different phrasing, different people) belong in the SAME group. Only group discussions together if they genuinely describe the same underlying pain point - do not merge distinct problems just because they are both software complaints or loosely related in topic.

Return ONLY a single JSON object (no markdown code fences, no commentary before or after) matching exactly this schema:
{"clusters": [{"label": string, "member_indices": [integer, ...]}]}

- "label" is a short canonical description of the shared underlying pain point for that group.
- "member_indices" lists every index (from the numbered list below) that belongs to that group.
- Every index from the list below must appear in exactly one cluster's member_indices.
- A discussion with no genuine duplicates among the others should be its own single-member cluster."""


def build_clustering_prompt(items: Sequence[Tuple[str, str]]) -> str:
    """Builds the prompt sent to the AI provider to cluster pain points.

    Args:
        items: One (description, evidence_quote) pair per discussion, in
            the same order their indices will be reported in the
            response - index 0 is items[0], etc.
    """
    lines: List[str] = []
    for i, (description, evidence_quote) in enumerate(items):
        lines.append(f"[{i}] Description: {description}")
        lines.append(f'    Evidence: "{evidence_quote}"')
    listing = "\n".join(lines)
    return f"{CLUSTERING_INSTRUCTIONS}\n\nDiscussions:\n{listing}"


EXTRACTION_SCHEMA_INSTRUCTIONS = """Return ONLY a single JSON object (no markdown code fences, no commentary before or after) matching exactly this schema:

{
  "primary_pain_point": {"description": string, "evidence_quote": string},
  "secondary_pain_points": [{"description": string, "evidence_quote": string}, ...],
  "user_persona": string,
  "feature_requests": [string, ...],
  "buying_signals": [string, ...],
  "emotional_sentiment": one of "Frustrated", "Angry", "Anxious", "Confused", "Neutral", "Hopeful", "Satisfied", "Excited",
  "urgency_score": integer 1-10,
  "opportunity_score": integer 1-100,
  "confidence": one of "Strong", "Moderate", "Weak",
  "startup_opportunity": string,
  "supporting_evidence": [string, ...]
}

CRITICAL RULES:
- Every "evidence_quote", every item in "supporting_evidence", and every item in "buying_signals" MUST be an exact, verbatim, contiguous substring of the discussion text below. Do not paraphrase or invent a quote. If no real quote supports a field, use an empty string or an empty list instead.
- "confidence" reflects how directly and unambiguously the primary pain point is stated in the text: "Strong" only if it is explicitly and clearly stated, "Moderate" if it is implied but reasonably clear, "Weak" if it required real inference to arrive at.
- "user_persona", "startup_opportunity", "opportunity_score", and "urgency_score" are your speculative extrapolation from limited evidence, not observed fact. Keep them reasonable and grounded in the text, but it is understood and expected that they are inferences, not verified conclusions — do not hedge them into vagueness, just don't invent details unrelated to the text.
- "secondary_pain_points", "feature_requests", and "buying_signals" may be empty lists if the text doesn't support any."""


KEYWORD_EXTRACTION_INSTRUCTIONS = """Extract 2-3 specific technical search keywords
from this user input for searching GitHub repositories.

User input: "{user_input}"

Rules:
- Return ONLY the keywords, nothing else
- No explanation, no punctuation
- 2-3 words maximum
- Focus on the technical domain
- Examples:
  "problems with invoice automation" -> "invoicing automation"
  "best saas ideas" -> "saas productivity"
  "current market pain problems" -> "developer tools"
  "I want to build something for payments" -> "payments fintech"
  "authentication is broken everywhere" -> "authentication security"
  "what are developers complaining about" -> "developer experience"

Keywords:"""


def build_keyword_extraction_prompt(user_input: str) -> str:
    """Builds the prompt sent to the AI provider to turn a free-text,
    natural-language description into a short GitHub search query.

    See src/insights/keyword_extraction.py for why the caller must
    still post-process the response rather than trusting "2-3 words,
    no punctuation" literally - verified against a real provider
    (Groq) that the instruction is a strong steer, not a guarantee.
    """
    return KEYWORD_EXTRACTION_INSTRUCTIONS.format(user_input=user_input)


def build_extraction_prompt(title: str, text: str, source_url: str) -> str:
    """Builds the prompt sent to the AI provider for a single discussion.

    Args:
        title: The discussion's title, if any (empty string if none).
        text: The discussion's body text — the only source of truth
            the model should quote from.
        source_url: Included for the model's context only; the model
            is never asked to quote from it.
    """
    title_line = f"Discussion title: {title}\n" if title else ""
    return (
        "You are analyzing a single online discussion for business "
        "research purposes. Extract structured information from the "
        "exact text provided below — do not use outside knowledge "
        "about the topic beyond what is written here.\n\n"
        f"{EXTRACTION_SCHEMA_INSTRUCTIONS}\n\n"
        f"{title_line}"
        "Discussion text:\n"
        '"""\n'
        f"{text}\n"
        '"""'
    )
