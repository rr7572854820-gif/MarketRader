"""Real AI provider, via Google's google-genai SDK (Gemini).

Only constructed by the factory (src/ai/__init__.py) when
config.gemini_configured is True. Nothing in here should be imported
directly by pipeline code — see src/ai/base.py.
"""

from __future__ import annotations

from src.ai.base import AIProvider, AIProviderError
from src.config import Config


class GeminiProvider(AIProvider):
    """Text generation via Google's Gemini API."""

    def __init__(self, config: Config) -> None:
        self._api_key = config.gemini_api_key
        self._model = config.gemini_model

    def check_connection(self) -> None:
        """Verify the API key works by listing available models —
        this does not consume any generation quota.
        """
        from google import genai

        try:
            client = genai.Client(api_key=self._api_key)
            next(iter(client.models.list()), None)
        except Exception as exc:
            raise AIProviderError(
                f"Gemini authentication/connection error ({type(exc).__name__})"
            ) from exc

    def generate_text(self, prompt: str) -> str:
        from google import genai

        try:
            client = genai.Client(api_key=self._api_key)
            response = client.models.generate_content(model=self._model, contents=prompt)
        except Exception as exc:
            raise AIProviderError(f"Gemini generation failed ({type(exc).__name__})") from exc

        if not response.text:
            raise AIProviderError("Gemini returned an empty response.")
        return response.text
