"""AI provider factory — the only place that decides which concrete
AIProvider implementation to use.

Everything else in the project must call get_ai_provider(config) and
depend only on AIProvider / AIProviderError — never import
GeminiProvider or MockAIProvider directly. That indirection is what
lets a future provider (Anthropic, OpenAI, Grok) be added by adding one
class and one branch here, with zero changes anywhere else.
"""

from __future__ import annotations

from src.ai.base import AIProvider, AIProviderError
from src.ai.gemini_provider import GeminiProvider
from src.ai.mock_provider import MockAIProvider
from src.config import Config

__all__ = ["AIProvider", "AIProviderError", "get_ai_provider"]


def get_ai_provider(config: Config) -> AIProvider:
    """Return the AIProvider appropriate for the current configuration.

    Real Gemini access is used only when config.gemini_configured is
    True; a MockAIProvider is returned automatically otherwise. No code
    change is needed to switch — set or unset GEMINI_API_KEY in .env.
    """
    if config.gemini_configured:
        return GeminiProvider(config)
    return MockAIProvider()
