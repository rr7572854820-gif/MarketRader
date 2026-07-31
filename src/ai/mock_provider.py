"""Mock AI provider — returns deterministic, schema-valid JSON instead of
calling any real AI backend.

Used automatically by the factory (src/ai/__init__.py) when
config.gemini_configured is False, so pipeline code (including the
Extractor's JSON parsing and the Aggregator's AI-assisted clustering)
can be built and exercised end-to-end without any AI provider
credentials at all.

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
