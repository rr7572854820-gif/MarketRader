"""Real AI provider, via Groq's OpenAI-compatible chat completions API.

Only constructed by the factory (src/ai/__init__.py) when
config.groq_configured is True. Nothing in here should be imported
directly by pipeline code — see src/ai/base.py.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Dict, List, Optional

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
    """Text generation via Groq's chat completions API.

    Key rotation: config.groq_api_keys (GROQ_API_KEY_1/2/3, see
    src/config.py) lets this provider fall through to the next
    configured key when the currently-active one hits Groq's rate limit
    (429) or is rejected (401) - both are key-specific problems a
    different key may not have. Falls back to the single legacy
    config.groq_api_key when no numbered keys are configured, so an
    existing single-key .env keeps working completely unchanged.

    Deliberately NOT rotated for a 5xx/connection error (_is_retryable) -
    those retry on the SAME key instead, exactly as before key rotation
    existed (see _generate_with_current_key). A server-side outage or
    network failure isn't a key-specific problem, so switching keys
    wouldn't plausibly fix it, and treating it as rotation-eligible
    would only burn through every configured key on a single transient
    blip.
    """

    def __init__(self, config: Config) -> None:
        self.api_keys = list(config.groq_api_keys)
        if not self.api_keys and config.groq_api_key:
            self.api_keys = [config.groq_api_key]
        if not self.api_keys:
            raise AIProviderError("No Groq API keys configured.")

        self.current_key_index = 0
        self._init_client()

    def _init_client(self) -> None:
        """(Re)builds self.client for the currently-active key - called
        once from __init__ and again from _rotate_key() each time the
        active key changes. Groq's own client is a lightweight HTTP
        wrapper (no persistent connection/session setup cost worth
        avoiding), so rebuilding it on rotation is simpler than trying
        to mutate an existing client's credentials in place.
        """
        self.client = Groq(api_key=self.api_keys[self.current_key_index])
        logger.info("Using Groq key %d/%d", self.current_key_index + 1, len(self.api_keys))

    def _rotate_key(self) -> bool:
        """Switches to the next configured key, if any.

        Returns:
            True if rotated to a new key (self.client is now that
                key's client). False if self.current_key_index was
                already the last configured key - nothing left to
                rotate to.
        """
        next_index = self.current_key_index + 1
        if next_index >= len(self.api_keys):
            logger.warning("All %d configured Groq API key(s) exhausted.", len(self.api_keys))
            return False

        self.current_key_index = next_index
        self._init_client()
        logger.info("Rotated to Groq key %d/%d", self.current_key_index + 1, len(self.api_keys))
        return True

    def check_connection(self) -> None:
        """Verify the currently-active key works by listing available
        models — this does not consume any generation quota. Checks
        only the active key (index 0 initially), not every configured
        key - the same lightweight "is my active configuration working"
        check this was before rotation existed, not a full audit of
        every key's validity.
        """
        try:
            next(iter(self.client.models.list().data), None)
        except Exception as exc:
            raise AIProviderError(
                f"Groq authentication/connection error ({type(exc).__name__})"
            ) from exc

    def generate_text(self, prompt: str) -> str:
        """Send a prompt to Groq and return its text response, rotating
        to the next configured key on a 429/401 (see class docstring).

        Raises:
            AIProviderAuthError: Every configured key was rejected (401).
            AIProviderRateLimitError: Every configured key hit Groq's
                rate limit (429).
            AIProviderError: Any other failure, after per-key retries
                (if applicable) are exhausted.
        """
        messages = [{"role": "user", "content": prompt}]
        # Byte size of the exact JSON body sent on the wire (api_key is
        # a header, never part of this payload, so there's nothing to
        # redact here) - logged for diagnosing payload-size-related
        # rejections without guessing at what the SDK actually sent.
        # Constant across every attempt/key (same prompt throughout),
        # so computed once rather than re-serialized every iteration.
        request_body_size = len(json.dumps({"model": _MODEL, "messages": messages}).encode("utf-8"))

        keys_tried = 0
        while keys_tried < len(self.api_keys):
            keys_tried += 1
            try:
                return self._generate_with_current_key(prompt, messages, request_body_size)
            except groq.AuthenticationError as exc:
                logger.warning("Groq key %d/%d invalid (401); rotating.", self.current_key_index + 1, len(self.api_keys))
                if not self._rotate_key():
                    raise AIProviderAuthError("All configured Groq API keys are invalid.") from exc
            except groq.RateLimitError as exc:
                logger.warning(
                    "Groq key %d/%d rate limited (429); rotating.", self.current_key_index + 1, len(self.api_keys)
                )
                if not self._rotate_key():
                    raise AIProviderRateLimitError("All configured Groq API keys are rate limited.") from exc

        # Unreachable in practice (the loop above always returns or
        # raises), but keeps type-checkers and readers honest about
        # what happens if that ever stops being true.
        raise AIProviderError(f"Groq generation failed: all {len(self.api_keys)} configured key(s) exhausted.")

    def _generate_with_current_key(self, prompt: str, messages: List[Dict[str, str]], request_body_size: int) -> str:
        """One key's worth of attempts - identical in shape to this
        method's pre-rotation self (retries only _is_retryable failures,
        same logging/redaction), except groq.AuthenticationError and
        groq.RateLimitError now propagate uncaught rather than being
        handled here, so generate_text()'s own loop can rotate keys for
        those two specifically.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_ATTEMPTS):
            logger.info(
                "Groq request: key=%d/%d model=%s prompt_chars=%d request_body_bytes=%d attempt=%d/%d",
                self.current_key_index + 1,
                len(self.api_keys),
                _MODEL,
                len(prompt),
                request_body_size,
                attempt + 1,
                _MAX_ATTEMPTS,
            )
            try:
                response = self.client.chat.completions.create(model=_MODEL, messages=messages)
            except (groq.AuthenticationError, groq.RateLimitError):
                raise  # handled by generate_text()'s own rotation loop, not here
            except Exception as exc:
                last_exc = exc
                status = getattr(exc, "status_code", type(exc).__name__)
                body = _redact_secret(_response_body(exc), self.api_keys[self.current_key_index])
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
