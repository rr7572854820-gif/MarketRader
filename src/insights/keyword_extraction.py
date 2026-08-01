"""Turns free-text, natural-language input into a short search query
for GitHubFetcher's Search Issues API (src/fetchers/github_fetcher.py).

Same shape as Aggregator's AI-assisted-with-deterministic-fallback
pattern (src/insights/aggregator.py): try the AI provider first, catch
only AIProviderError (the one exception type this package's boundary
allows a caller to depend on — see src/ai/base.py), and fall back to a
simple, always-available heuristic rather than ever raising. A user
typing a plain-English description of a problem (e.g. "I keep hearing
about invoice automation pain") is not, by itself, a usable GitHub
Search Issues query — this exists so GitHubFetcher's own keyword
requirement can be satisfied without asking the user to already know
which technical terms to type.

Only used by src/pipeline/pipeline.py, and only for source="github" —
see PipelineConfig.keyword's docstring. GitHubFetcher itself has no AI
dependency and never will (see its own module docstring on the
Fetch-stage-is-AI-free architecture); this module exists precisely so
that invariant doesn't have to be broken to get this feature.
"""

from __future__ import annotations

import logging
import re
from typing import List

from src.ai.base import AIProvider, AIProviderError
from src.insights.prompts import build_keyword_extraction_prompt

logger = logging.getLogger(__name__)

_MAX_WORDS = 3
_FALLBACK_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "with", "for", "of", "in", "on",
    "to", "and", "or", "i", "we", "you", "your", "my", "me", "want", "wanted",
    "need", "needed", "looking", "look", "find", "about", "what", "whats",
    "current", "best", "something", "problems", "problem", "issues", "issue",
    "related", "stuff", "these", "days", "lately", "up", "out", "at", "it",
    "that", "this", "there", "here", "just", "like", "some", "any", "all",
}
_GENERIC_FALLBACK = "software"

_QUOTE_STRIP_CHARS = "\"'` .,:;"
_WORD_STRIP_CHARS = ".,;:!?\"'"


def extract_search_terms(user_input: str, ai_provider: AIProvider) -> str:
    """Returns a short (<=3 word) GitHub Search Issues query derived
    from user_input, via one AI call with a deterministic fallback.

    Never raises: any AIProviderError (an invalid key, rate limit,
    provider outage, malformed/empty response) falls back to
    _fallback_extract_search_terms instead of propagating, since a
    keyword-extraction failure should degrade to a naive-but-usable
    query, not abort the whole GitHub search - the same reasoning
    Aggregator applies to a failed clustering call.
    """
    try:
        raw = ai_provider.generate_text(build_keyword_extraction_prompt(user_input))
    except AIProviderError as exc:
        logger.warning(
            "Keyword extraction AI call failed (%s); falling back to naive extraction.", type(exc).__name__
        )
        return _fallback_extract_search_terms(user_input)

    cleaned = _clean_ai_response(raw)
    if not cleaned:
        logger.warning("Keyword extraction returned no usable text; falling back to naive extraction.")
        return _fallback_extract_search_terms(user_input)
    return cleaned


def _clean_ai_response(raw: str) -> str:
    """Real providers do not reliably follow "return ONLY the
    keywords, 2-3 words maximum" - confirmed against a real Groq call,
    which returned multiple newline-separated candidate phrases despite
    the prompt's explicit instructions (e.g.
    "invoice automation\\ninvoicing\\nsaas" for one input). The first
    non-blank line was consistently the intended answer in every case
    observed, so that's what's used; word count is enforced here
    (capped, not trusted to the model), not assumed from the prompt.
    """
    first_line = next((line.strip() for line in raw.splitlines() if line.strip()), "")
    first_line = first_line.strip(_QUOTE_STRIP_CHARS)

    # A model that echoes the "Keywords:" label back despite being
    # told not to - defensive, same spirit as Aggregator's markdown
    # code-fence stripping for a response that ignores instructions.
    prefix, sep, rest = first_line.partition(":")
    if sep and prefix.strip().lower() in {"keyword", "keywords"}:
        first_line = rest.strip()

    words: List[str] = [w.strip(_WORD_STRIP_CHARS) for w in first_line.split()]
    words = [w for w in words if w]
    return " ".join(words[:_MAX_WORDS])


def _fallback_extract_search_terms(user_input: str) -> str:
    """Deterministic, zero-cost fallback: strip common English
    stopwords, take up to _MAX_WORDS meaningful words in their
    original order. Always returns a non-empty string -
    GitHubFetcher.fetch() requires a non-blank keyword, so an empty
    result here would silently break the entire GitHub search path.
    """
    words = re.findall(r"[a-zA-Z0-9']+", user_input.lower())
    meaningful = [w for w in words if w not in _FALLBACK_STOPWORDS and len(w) > 2]
    if not meaningful:
        meaningful = words if words else [_GENERIC_FALLBACK]
    return " ".join(meaningful[:_MAX_WORDS])
