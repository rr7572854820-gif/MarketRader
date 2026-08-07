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

# Raised from 3 to 8 - requested to dramatically improve expansion
# quality (product names + technical terms + pain points, not just
# generic paraphrases). Confirmed via AskUserQuestion before raising
# this: GitHubFetcher._discover_issues() issues one GitHub Search API
# call per term (src/fetchers/github_fetcher.py), so this ~triples
# GitHub API usage per run against an already-exhausted, actively-
# tracked unauthenticated rate limit (TODO.md), and more discovered
# discussions also means more load on the separately-unresolved Groq
# burst-concurrency rate-limit problem (TODO.md, three prior tasks).
# Neither is fixable from this file; implemented as explicitly
# specified, with both risks documented as new TODO.md items rather
# than silently absorbed. The prior 4->3 reduction (see git history)
# was itself never proven to cause its intended clustering effect
# (TODO.md), so this isn't a confirmed regression of a verified fix -
# just a real, separate, mechanically-certain rate-limit cost.
_DEFAULT_MAX_TERMS = 8


def _build_expansion_prompt(user_input: str, max_terms: int) -> str:
    return f"""You are a market research expert.
Convert this topic into {max_terms} specific search terms that will find real user complaints on GitHub and HackerNews.

Topic: "{user_input}"

Think like this:
1. What are the main tools/products in this space?
2. What are the technical terms developers use?
3. What are related pain points?
4. What companies solve this problem?

Rules:
- Return {max_terms} terms
- Mix: product names + technical terms + pain points
- Never generic words: best, ideas, problems, tool
- Return ONLY valid JSON array
- No explanation, no markdown

The examples below show the required style only - they are not related to
the actual topic above. Do not reuse their words, and do not repeat any
of them in your answer; generate terms specific to "{user_input}" only.

"payments" ->
["stripe checkout", "payment gateway timeout",
 "billing subscription saas", "invoice generation",
 "paypal integration", "refund processing",
 "credit card declined", "checkout flow"]

"authentication" ->
["oauth2 implementation", "jwt token expiry",
 "sso login saas", "auth0 alternative",
 "user authentication", "refresh token",
 "okta integration", "login security"]

"invoicing" ->
["invoice generation saas", "invoiceninja",
 "billing automation", "accounts receivable",
 "e-invoicing compliance", "gst invoice",
 "pdf invoice", "recurring billing"]

"developer tools" ->
["vscode extension", "github copilot alternative",
 "code review tool", "ci cd pipeline",
 "developer productivity", "debugging tool",
 "api testing", "code quality"]

Output JSON array of exactly {max_terms} terms for "{user_input}":"""


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
