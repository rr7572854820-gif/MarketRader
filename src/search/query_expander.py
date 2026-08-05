"""Converts one free-text user query into several related search terms,
via one AI call with a deterministic fallback.

Same AI-assisted-with-fallback shape as
src/insights/keyword_extraction.py's extract_search_terms() (try the
provider, catch only AIProviderError, degrade to something always-
available rather than ever raising) - not a coincidence, this is the
project's established pattern for "AI call whose failure must never
abort the pipeline" (see also src/insights/aggregator.py's clustering
fallback). As of this task, QueryExpander.expand() has REPLACED
extract_search_terms() as the mechanism that derives GitHub's actual
search keyword in src/pipeline/pipeline.py - only the first of its
returned terms is used for now (see Pipeline.run()), since
GitHubFetcher does not yet accept multiple search terms. See TODO.md
for why extract_search_terms()/keyword_extraction.py itself is left
in place, unused on this path, rather than deleted.
"""

from __future__ import annotations

import json
import logging
import re
from typing import List

from src.ai.base import AIProvider, AIProviderError

logger = logging.getLogger(__name__)

_DEFAULT_MAX_TERMS = 4


def _build_expansion_prompt(user_input: str, max_terms: int) -> str:
    return f"""Convert ONE user input into {max_terms} specific search terms for finding GitHub repositories and discussions where real users report problems.

One example, showing the required format only - do not reuse its words, and do not repeat this example in your answer:
input: "stripe payments broken"
output: ["stripe api integration", "payment processing saas", "billing system errors"]

Now convert this input, and only this input:
"{user_input}"

Rules:
- Each term finds DIFFERENT related content
- Every term must relate to "{user_input}" specifically, not to the example above
- Never include generic words: best, ideas, problems, current, pain, market, what, how
- Focus on the business or technical domain
- Return ONLY a valid JSON array of {max_terms} strings, nothing else
- No explanation, no markdown, no backticks, no nested arrays, no extra keys

Output (JSON array only):"""


class QueryExpander:
    """Converts one user query into multiple related search terms.

    Works automatically for ALL sources: GitHub, HN, Reddit,
    ProductHunt. Zero extra work when adding new sources - this
    operates purely on the input string, with no source-specific logic.
    """

    def __init__(self, ai_provider: AIProvider) -> None:
        self.ai = ai_provider

    def expand(self, user_input: str, max_terms: int = _DEFAULT_MAX_TERMS) -> List[str]:
        """Returns up to max_terms related search terms.

        ALWAYS returns at least [user_input] even if the AI call fails
        completely, its response isn't valid JSON, or it returns
        nothing usable. Never raises.
        """
        prompt = _build_expansion_prompt(user_input, max_terms)

        try:
            response = self.ai.generate_text(prompt)
        except AIProviderError as exc:
            logger.warning(
                "Query expansion AI call failed (%s); falling back to: %r", type(exc).__name__, user_input
            )
            return [user_input]

        try:
            clean = response.strip()
            # Remove markdown code blocks if present.
            if "```" in clean:
                parts = clean.split("```")
                clean = parts[1] if len(parts) > 1 else clean
                if clean.lower().startswith("json"):
                    clean = clean[4:]
            terms = json.loads(clean.strip())
        except (json.JSONDecodeError, AttributeError) as exc:
            # AttributeError covers a non-string response (e.g. a stub
            # provider returning None) reaching .strip() above - a real
            # provider always returns str per AIProvider's contract,
            # but this fallback must hold even if that's ever violated.
            #
            # A real Groq call also sometimes ignores the "JSON array
            # only" instruction and returns a curly-brace pseudo-list
            # with no colons (e.g. {"term one", "term two"}), which
            # isn't valid JSON at all. Recover the quoted substrings
            # directly from its own response rather than giving up -
            # these are terms the model actually produced, not invented.
            recovered = [m.strip() for m in re.findall(r'"([^"]{3,80})"', response)]
            valid = [t for t in recovered if len(t) > 2]
            if valid:
                logger.warning(
                    "Query expansion output wasn't valid JSON (%s); recovered %d quoted term(s) from raw text",
                    type(exc).__name__,
                    len(valid),
                )
                return valid[:max_terms]

            logger.warning(
                "Query expansion returned unparseable output (%s); falling back to: %r", type(exc).__name__, user_input
            )
            return [user_input]

        if isinstance(terms, list):
            valid = [str(t).strip() for t in terms if isinstance(t, str) and len(t.strip()) > 2]
            if valid:
                return valid[:max_terms]

        if isinstance(terms, dict) and terms and all(isinstance(v, str) for v in terms.values()):
            # A real Groq call sometimes wraps the array in a redundant
            # {"term": "term", ...} object despite the prompt asking for
            # a plain array - the values are still the model's actual
            # output, not fabricated. Deliberately NOT falling back to
            # dict keys when values aren't all strings: a differently-
            # shaped JSON object (e.g. this project's clustering
            # response shape, {"clusters": [...]}) has keys that are
            # schema field names, not search terms, and using them
            # would silently replace the user's query with a fake one.
            valid = [v.strip() for v in terms.values() if len(v.strip()) > 2]
            if valid:
                return valid[:max_terms]

        logger.warning("Query expansion returned invalid format. Using original.")
        return [user_input]
