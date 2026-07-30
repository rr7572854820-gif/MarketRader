"""Tests for src/ai/mock_provider.py and the get_ai_provider factory's
branching - neither had a dedicated test file before Task 9.
GeminiProvider itself is not exercised here (it needs a real API call);
only that the factory returns the right type without ever contacting
the real Gemini API (GeminiProvider's __init__ just stores config, no
network call, so constructing one here is safe).
"""

from __future__ import annotations

import json

from src.ai import get_ai_provider
from src.ai.gemini_provider import GeminiProvider
from src.ai.mock_provider import MockAIProvider, MOCK_RESPONSE_PREFIX
from src.config import Config


def _config(gemini_configured: bool) -> Config:
    return Config(
        gemini_api_key="a-real-looking-key" if gemini_configured else None,
        gemini_model="gemini-flash-latest",
        reddit_client_id=None,
        reddit_client_secret=None,
        reddit_user_agent="test-agent",
    )


# --- MockAIProvider ------------------------------------------------------------


def test_mock_provider_check_connection_never_raises():
    MockAIProvider().check_connection()  # must not raise


def test_mock_provider_response_is_clearly_labeled():
    response = MockAIProvider().generate_text("any prompt")
    assert response.startswith(MOCK_RESPONSE_PREFIX)


def test_mock_provider_response_is_never_valid_json():
    """This is the exact assumption src/pipeline/cache.py's
    CachingAIProvider relies on to guarantee mock runs never cache
    anything (see tests/test_cache.py) - worth asserting directly here
    too, at the source, rather than only indirectly downstream.
    """
    response = MockAIProvider().generate_text("any prompt")
    try:
        json.loads(response)
        is_json = True
    except json.JSONDecodeError:
        is_json = False
    assert not is_json


# --- get_ai_provider factory ----------------------------------------------------


def test_factory_returns_mock_provider_when_gemini_not_configured():
    provider = get_ai_provider(_config(gemini_configured=False))
    assert isinstance(provider, MockAIProvider)


def test_factory_returns_gemini_provider_when_gemini_configured():
    provider = get_ai_provider(_config(gemini_configured=True))
    assert isinstance(provider, GeminiProvider)


def test_factory_force_mock_overrides_configured_gemini():
    provider = get_ai_provider(_config(gemini_configured=True), force_mock=True)
    assert isinstance(provider, MockAIProvider)
