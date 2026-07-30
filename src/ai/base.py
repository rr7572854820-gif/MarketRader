"""The AIProvider interface every AI backend must implement.

Nothing outside this package should import a concrete provider
(GeminiProvider, MockAIProvider, or any future AnthropicProvider /
OpenAIProvider / GrokProvider) directly. Everything else — the analysis
pipeline (Extractor, Grouper, ...), CLI commands, tests — should depend
only on this interface, on AIProviderError, and on the factory in
src/ai/__init__.py. Adding a new provider later means adding one new
class here and one branch in the factory; it should never require
touching code that consumes AI output.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class AIProviderError(Exception):
    """Raised by any AIProvider implementation when a call fails.

    Callers should catch this one type and never a provider-specific
    exception (e.g. an error from google-genai) — that's what keeps
    calling code provider-agnostic.
    """


class AIProvider(ABC):
    """Common interface for a text-generation AI backend."""

    @abstractmethod
    def check_connection(self) -> None:
        """Verify that credentials/configuration actually work.

        Implementations should avoid spending real usage/quota where
        the underlying API offers a free way to check (e.g. listing
        models instead of generating text).

        Raises:
            AIProviderError: If the connection/credentials are invalid.
        """
        raise NotImplementedError

    @abstractmethod
    def generate_text(self, prompt: str) -> str:
        """Send a prompt and return the model's raw text response.

        This is the only method later pipeline stages (Extractor,
        Grouper) are allowed to call — never a provider-specific client.

        Raises:
            AIProviderError: If the call fails for any reason.
        """
        raise NotImplementedError
