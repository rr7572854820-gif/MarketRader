"""Real AI provider, via Groq's OpenAI-compatible chat completions API.

Only constructed by the factory (src/ai/__init__.py) when
config.groq_configured is True. Nothing in here should be imported
directly by pipeline code — see src/ai/base.py.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

import groq
from groq import Groq

from src.ai.base import AIProvider, AIProviderError
from src.ai.exceptions import AIProviderAuthError, AIProviderRateLimitError
from src.config import Config

logger = logging.getLogger(__name__)

# llama3-8b-8192 was decommissioned by Groq (confirmed via a real call:
# 400 model_decommissioned, see https://console.groq.com/docs/deprecations)
# - llama-3.1-8b-instant is its direct successor in Groq's own model
# list (same Meta 8B "instant" tier, still the fastest/highest-free-
# tier option), confirmed live via client.models.list() and a real
# generate_text() call before switching.
_MODEL = "llama-3.1-8b-instant"
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


def _response_body(exc: Exception) -> str:
    """The exact response body Groq sent back, when available - e.g.
    {"error":{"message":"...","type":"invalid_request_error","code":"model_decommissioned"}}
    for a 400. groq.APIStatusError carries the raw httpx.Response on
    `.response`; falls back to str(exc) for exception types that don't
    (e.g. APIConnectionError, which never got a response at all).
    """
    response = getattr(exc, "response", None)
    if response is not None and hasattr(response, "text"):
        return response.text
    return str(exc)


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
        messages = [{"role": "user", "content": prompt}]
        # Byte size of the exact JSON body sent on the wire (api_key is
        # a header, never part of this payload, so there's nothing to
        # redact here) - logged for diagnosing payload-size-related
        # rejections without guessing at what the SDK actually sent.
        # Constant across retries (same prompt each attempt), so
        # computed once rather than re-serialized every loop iteration.
        request_body_size = len(json.dumps({"model": _MODEL, "messages": messages}).encode("utf-8"))
        for attempt in range(_MAX_ATTEMPTS):
            logger.info(
                "Groq request: model=%s prompt_chars=%d request_body_bytes=%d attempt=%d/%d",
                _MODEL,
                len(prompt),
                request_body_size,
                attempt + 1,
                _MAX_ATTEMPTS,
            )
            try:
                client = Groq(api_key=self._api_key)
                response = client.chat.completions.create(model=_MODEL, messages=messages)
            except groq.AuthenticationError as exc:
                logger.error("Groq authentication error (401): %s", _redact_secret(_response_body(exc), self._api_key))
                raise AIProviderAuthError("Groq API key is invalid.") from exc
            except groq.RateLimitError as exc:
                logger.error("Groq rate limit error (429): %s", _redact_secret(_response_body(exc), self._api_key))
                raise AIProviderRateLimitError("Groq rate limit exceeded.") from exc
            except Exception as exc:
                last_exc = exc
                status = getattr(exc, "status_code", type(exc).__name__)
                body = _redact_secret(_response_body(exc), self._api_key)
                logger.error(
                    "Groq chat completion failed: status=%s type=%s model=%s prompt_chars=%d response_body=%s",
                    status,
                    type(exc).__name__,
                    _MODEL,
                    len(prompt),
                    body,
                )
                if _is_retryable(exc) and attempt < _MAX_ATTEMPTS - 1:
                    time.sleep(_BASE_DELAY_SECONDS * (2**attempt))
                    continue
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
