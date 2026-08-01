"""Mock AI provider — returns deterministic, schema-valid JSON instead of
calling any real AI backend.

Used automatically by the factory (src/ai/__init__.py) when
config.gemini_configured is False, so pipeline code (including the
Extractor's JSON parsing, the Aggregator's AI-assisted clustering, and
Pipeline.run()'s GitHub keyword extraction - see
src/insights/keyword_extraction.py) can be built and exercised
end-to-end without any AI provider credentials at all.

Schema fix: this used to return a fixed, obviously-non-JSON sentence.
That satisfied "never mistaken for a genuine finding" but also meant
every extraction failed JSON parsing and every clustering call fell
back to lexical overlap - the mock path never actually exercised the
real parsing/verification logic it exists to stand in for. Now it
returns JSON matching the exact schemas Extractor and Aggregator expect
(src/insights/prompts.py's EXTRACTION_SCHEMA_INSTRUCTIONS and
CLUSTERING_INSTRUCTIONS), with every evidence_quote/supporting_evidence
value a real, verbatim substring pulled from the prompt's own embedded
discussion text - never invented - so it passes the same
quote-verification guardrail (extractor.py::_verified_quote) a real
provider's honest output would.
"""

from __future__ import annotations

import json
import re

from src.ai.base import AIProvider

MOCK_RESPONSE_PREFIX = "[MOCK AI RESPONSE - no real provider configured]"

# build_extraction_prompt (src/insights/prompts.py) always wraps the
# source discussion text in a `"""`-delimited block at the end of the
# prompt; build_clustering_prompt never does. Presence of this block is
# what tells generate_text which schema to answer with.
_DISCUSSION_TEXT_RE = re.compile(r'Discussion text:\n"""\n(.*)\n"""\s*$', re.DOTALL)

# build_clustering_prompt lists discussions as lines like
# "[0] Description: ...", one per discussion, in index order.
_CLUSTER_INDEX_RE = re.compile(r"^\[(\d+)\]", re.MULTILINE)

# build_keyword_extraction_prompt (src/insights/prompts.py) is the only
# prompt shape containing this exact phrase - checked before the two
# regexes above since it doesn't match either of them (a keyword-
# extraction prompt has no "Discussion text:" block and no "[N]" index
# lines), so without this check it would silently fall through to
# _clustering_response and return an unrelated, useless JSON blob.
_KEYWORD_EXTRACTION_MARKER = "specific technical search keywords"
# [^\n]* (not DOTALL .*) deliberately - the prompt's few-shot examples
# also contain quoted strings later on, so a greedy DOTALL match here
# would capture everything up to the LAST quote in the whole prompt
# (inside those examples) instead of just this one line - found by
# a real failing test (a real "invoicing" input was wrongly matched
# with an unrelated example word "rules" from later in the prompt).
_KEYWORD_EXTRACTION_INPUT_RE = re.compile(r'User input: "([^\n]*)"')


class MockAIProvider(AIProvider):
    """Always "succeeds" and returns deterministic, schema-valid JSON.

    Every field that Extractor/Aggregator treat as evidence (quotes)
    comes verbatim from the prompt's own source text, never invented.
    Every field treated as speculative inference (user_persona,
    startup_opportunity, and the primary pain point's description) is
    prefixed with MOCK_RESPONSE_PREFIX and pinned to the most
    conservative score/confidence values, so nothing downstream can
    mistake this for a genuine model finding just by reading the field
    - on top of post.is_mock already flagging the source structurally.
    """

    def check_connection(self) -> None:
        return  # nothing to check — there's no real backend behind this

    def generate_text(self, prompt: str) -> str:
        if _KEYWORD_EXTRACTION_MARKER in prompt:
            return self._keyword_extraction_response(prompt)
        match = _DISCUSSION_TEXT_RE.search(prompt)
        if match is not None:
            return self._extraction_response(match.group(1).strip())
        return self._clustering_response(prompt)

    def _extraction_response(self, source_text: str) -> str:
        quote = _first_sentence(source_text) if source_text else ""
        return json.dumps(
            {
                "primary_pain_point": {
                    "description": f"{MOCK_RESPONSE_PREFIX} placeholder pain point",
                    "evidence_quote": quote,
                },
                "secondary_pain_points": [],
                "user_persona": f"{MOCK_RESPONSE_PREFIX} placeholder persona",
                "feature_requests": [],
                "buying_signals": [],
                "emotional_sentiment": "Neutral",
                "urgency_score": 1,
                "opportunity_score": 1,
                "confidence": "Weak",
                "startup_opportunity": f"{MOCK_RESPONSE_PREFIX} not a real recommendation",
                "supporting_evidence": [quote] if quote else [],
            }
        )

    def _keyword_extraction_response(self, prompt: str) -> str:
        """Deliberately NOT prefixed with MOCK_RESPONSE_PREFIX like the
        other speculative fields above. Those are displayed to the user
        as-is, so the prefix keeps them recognizably fake; this value
        instead gets consumed internally to drive a real GitHub Search
        Issues API call (src/insights/keyword_extraction.py) - a
        prefixed response would make that real search essentially
        non-functional for the legitimate case of running a mock AI
        provider against a real GitHub fetch (real data, no AI cost).
        Returns a plausible short phrase using the same naive-
        extraction shape keyword_extraction.py's own fallback uses,
        not a schema-driven response - there's no JSON schema for this
        prompt, unlike extraction/clustering.
        """
        match = _KEYWORD_EXTRACTION_INPUT_RE.search(prompt)
        user_input = match.group(1) if match else ""
        words = re.findall(r"[a-zA-Z0-9']+", user_input.lower())
        meaningful = [w for w in words if len(w) > 3][:2]
        return " ".join(meaningful) if meaningful else "software"

    def _clustering_response(self, prompt: str) -> str:
        # One singleton cluster per discussion — a mock has no real
        # semantic judgment to offer, so it makes no merge decision
        # rather than fabricating one. Still exercises the real
        # AI-clustering parse path in Aggregator instead of triggering
        # its lexical fallback.
        indices = [int(i) for i in _CLUSTER_INDEX_RE.findall(prompt)]
        clusters = [
            {"label": f"{MOCK_RESPONSE_PREFIX} placeholder cluster", "member_indices": [i]}
            for i in indices
        ]
        return json.dumps({"clusters": clusters})


def _first_sentence(text: str) -> str:
    """Returns a real, verbatim prefix of text — never a paraphrase —
    usable as a verified evidence quote, since MockAIProvider must
    satisfy the same non-fabrication guardrail a real provider does.
    """
    period = text.find(". ")
    if period == -1:
        period = text.find(".")
    return text[: period + 1] if period != -1 else text
