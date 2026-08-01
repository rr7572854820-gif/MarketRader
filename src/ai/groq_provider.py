"""Real AI provider, via Groq's OpenAI-compatible chat completions API.

Only constructed by the factory (src/ai/__init__.py) when
config.groq_configured is True. Nothing in here should be imported
directly by pipeline code — see src/ai/base.py.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import groq
from groq import Groq

from src.ai.base import AIProvider, AIProviderError
from src.ai.exceptions import AIProviderAuthError, AIProviderRateLimitError
from src.config import Config

logger = logging.getLogger(__name__)

_MODEL = "llama3-8b-8192"  # fastest Groq model, highest free-tier limits
_MAX_ATTEMPTS = 3
_BASE_DELAY_SECONDS = 1.0
_REDACTED = "<redacted>"


def _redact_secret(text: str, secret: Optional[str]) -> str:
    """Strips a known secret value (e.g. the API key) out of an error
    string before it's logged or raised — same diagnostic-only helper
    as gemini_provider.py's, for the same reason.
    """
    if secret:
        return text.replace(secret, _REDACTED)
    return text


def _is_retryable(exc: Exception) -> bool:
    """True for transient failures worth retrying: Groq's own 5xx
    server errors and network-level connection/timeout errors.
    Confirmed against the real groq package's exception hierarchy
    (groq._exceptions.APIStatusError.status_code, APIConnectionError)
    rather than guessed. 401 and 429 are handled as their own
    immediate, non-retried cases in generate_text - a bad key won't
    become valid on retry, and this task's 429 handling is a direct
    1:1 status-to-exception mapping, not a retry-then-raise policy.
    """
    if isinstance(exc, groq.APIConnectionError):
        return True
    if isinstance(exc, groq.APIStatusError) and exc.status_code >= 500:
        return True
    return False


class GroqProvider(AIProvider):
    """Text generation via Groq's chat completions API."""

    def __init__(self, config: Config) -> None:
        self._api_key = config.groq_api_key

    def check_connection(self) -> None:
        """Verify the API key works by listing available models —
        this does not consume any generation quota.
        """
        try:
            client = Groq(api_key=self._api_key)
            next(iter(client.models.list().data), None)
        except Exception as exc:
            raise AIProviderError(
                f"Groq authentication/connection error ({type(exc).__name__})"
            ) from exc

    def generate_text(self, prompt: str) -> str:
        """Send a prompt to Groq and return its text response.

        Retries transient failures (5xx, network errors) up to
        _MAX_ATTEMPTS times with exponential backoff before giving up.

        Raises:
            AIProviderAuthError: The API key was rejected (401).
            AIProviderRateLimitError: Groq's rate limit was hit (429).
            AIProviderError: Any other failure, after retries (if
                applicable) are exhausted.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                client = Groq(api_key=self._api_key)
                response = client.chat.completions.create(
                    model=_MODEL, messages=[{"role": "user", "content": prompt}]
                )
            except groq.AuthenticationError as exc:
                raise AIProviderAuthError("Groq API key is invalid.") from exc
            except groq.RateLimitError as exc:
                raise AIProviderRateLimitError("Groq rate limit exceeded.") from exc
            except Exception as exc:
                last_exc = exc
                if _is_retryable(exc) and attempt < _MAX_ATTEMPTS - 1:
                    time.sleep(_BASE_DELAY_SECONDS * (2**attempt))
                    continue
                detail = _redact_secret(str(exc), self._api_key)
                logger.error("Groq chat completion failed (%s): %s", type(exc).__name__, detail)
                status = getattr(exc, "status_code", type(exc).__name__)
                raise AIProviderError(f"Groq error: {status}") from exc
            else:
                text = response.choices[0].message.content if response.choices else None
                if not text:
                    raise AIProviderError("Groq returned an empty response.")
                return text

        # Unreachable in practice (the loop above always returns or
        # raises), but keeps type-checkers and readers honest about
        # what happens if that ever stops being true.
        raise AIProviderError(
            f"Groq generation failed after {_MAX_ATTEMPTS} attempts "
            f"({type(last_exc).__name__ if last_exc else 'unknown error'})"
        )
