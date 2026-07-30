"""Mock AI provider — returns clearly-labeled fixed text instead of
calling any real AI backend.

Used automatically by the factory (src/ai/__init__.py) when
config.gemini_configured is False, so pipeline code can be built and
exercised without any AI provider credentials at all.
"""

from __future__ import annotations

from src.ai.base import AIProvider

MOCK_RESPONSE_PREFIX = "[MOCK AI RESPONSE - no real provider configured]"


class MockAIProvider(AIProvider):
    """Always "succeeds" and returns a fixed, obviously-fake response.

    Never produces anything that could be mistaken for a real model
    output — every response is prefixed with MOCK_RESPONSE_PREFIX so
    calling code (and a human reading logs) can never confuse this for
    a genuine finding.
    """

    def check_connection(self) -> None:
        return  # nothing to check — there's no real backend behind this

    def generate_text(self, prompt: str) -> str:
        return (
            f"{MOCK_RESPONSE_PREFIX} This is placeholder text standing in "
            f"for a real model's output. It must never be treated as a "
            f"genuine finding."
        )
