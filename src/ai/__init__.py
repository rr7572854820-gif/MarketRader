"""AI provider factory — the only place that decides which concrete
AIProvider implementation to use.

Everything else in the project must call get_ai_provider(config) and
depend only on AIProvider / AIProviderError — never import
GeminiProvider, GroqProvider, or MockAIProvider directly. That
indirection is what lets a future provider (Anthropic, OpenAI) be added
by adding one class and one branch here, with zero changes anywhere else.
"""

from __future__ import annotations

from src.ai.base import AIProvider, AIProviderError
from src.ai.gemini_provider import GeminiProvider
from src.ai.groq_provider import GroqProvider
from src.ai.mock_provider import MockAIProvider
from src.config import Config

__all__ = ["AIProvider", "AIProviderError", "get_ai_provider"]


def get_ai_provider(config: Config, *, force_mock: bool = False) -> AIProvider:
    """Return the AIProvider appropriate for the current configuration.

    Priority order: Groq (if config.groq_configured) -> Gemini (if
    config.gemini_configured) -> MockAIProvider. Groq wins first when
    both are configured, per this project's explicit choice to default
    to Groq's faster/higher free-tier limits over Gemini once a real
    Groq key exists - not a quality judgment between the two models,
    just the stated default. No code change is needed to switch which
    real provider is used — set/unset GROQ_API_KEY / GEMINI_API_KEY in
    .env.

    Args:
        force_mock: If True, always returns MockAIProvider regardless
            of config — e.g. for a CLI --mock flag (see
            src/pipeline/). This is the sanctioned way to force mock
            mode; still never construct MockAIProvider directly
            outside this factory.
    """
    if force_mock:
        return MockAIProvider()
    if config.groq_configured:
        return GroqProvider(config)
    if config.gemini_configured:
        return GeminiProvider(config)
    return MockAIProvider()
