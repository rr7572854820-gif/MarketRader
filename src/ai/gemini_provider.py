"""Real AI provider, via Google's google-genai SDK (Gemini).

Only constructed by the factory (src/ai/__init__.py) when
config.gemini_configured is True. Nothing in here should be imported
directly by pipeline code — see src/ai/base.py.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from src.ai.base import AIProvider, AIProviderError
from src.config import Config

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BASE_DELAY_SECONDS = 1.0
_REDACTED = "<redacted>"


def _redact_secret(text: str, secret: Optional[str]) -> str:
    """Strips a known secret value (e.g. the API key) out of an error
    string before it's logged or raised. Diagnostic-only helper - see
    generate_text's exception handling below (temporary investigation,
    not a permanent behavior change).
    """
    if secret:
        return text.replace(secret, _REDACTED)
    return text


def _is_retryable(exc: Exception) -> bool:
    """True for transient failures worth retrying: 5xx server errors,
    and 429 rate limiting. Confirmed against the real google-genai
    error hierarchy (google.genai.errors.APIError -> ClientError /
    ServerError, with .code holding the HTTP status) rather than
    guessed — see SESSION.md for how this was checked. Any other
    ClientError (401, 403, 404, ...) is a permanent problem retrying
    won't fix.
    """
    from google.genai import errors

    if isinstance(exc, errors.ServerError):
        return True
    if isinstance(exc, errors.ClientError) and getattr(exc, "code", None) == 429:
        return True
    return False


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
        """Send a prompt to Gemini and return its text response.

        Retries transient failures (5xx, 429 rate limiting) up to
        _MAX_ATTEMPTS times with exponential backoff before giving up.
        Any other failure (bad API key, invalid model name, etc.) is
        not retried, since retrying wouldn't change the outcome.
        """
        from google import genai

        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                client = genai.Client(api_key=self._api_key)
                response = client.models.generate_content(model=self._model, contents=prompt)
            except Exception as exc:
                last_exc = exc
                if _is_retryable(exc) and attempt < _MAX_ATTEMPTS - 1:
                    time.sleep(_BASE_DELAY_SECONDS * (2**attempt))
                    continue
                # TEMPORARY diagnostic instrumentation (investigation only,
                # not a permanent behavior change): surfaces the SDK's own
                # error detail instead of just the exception type name, so
                # the real root cause (bad key vs. quota vs. model-not-
                # found vs. something else) is actually visible. The API
                # key itself is redacted defensively in case the SDK ever
                # echoes request details back in an error message.
                detail = _redact_secret(str(exc), self._api_key)
                logger.error("Gemini generate_content failed (%s): %s", type(exc).__name__, detail)
                raise AIProviderError(f"Gemini generation failed ({type(exc).__name__}): {detail}") from exc
            else:
                if not response.text:
                    raise AIProviderError("Gemini returned an empty response.")
                return response.text

        # Unreachable in practice (the loop above always returns or
        # raises), but keeps type-checkers and readers honest about
        # what happens if that ever stops being true.
        raise AIProviderError(
            f"Gemini generation failed after {_MAX_ATTEMPTS} attempts "
            f"({type(last_exc).__name__ if last_exc else 'unknown error'})"
        )
