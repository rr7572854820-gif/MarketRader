"""Tests for src/ai/groq_provider.py and its factory branch (Groq ->
Gemini -> Mock priority) in get_ai_provider(). Every Groq API call is
mocked via patching src.ai.groq_provider.Groq - never hits the real
Groq API. GeminiProvider itself is not exercised for real either (same
existing precedent as tests/test_ai_providers.py - its __init__ just
stores config, no network call, so constructing one to check isinstance
is safe).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import groq
import pytest

from src.ai import get_ai_provider
from src.ai.exceptions import AIProviderAuthError, AIProviderRateLimitError
from src.ai.gemini_provider import GeminiProvider
from src.ai.groq_provider import GroqProvider
from src.config import Config


def _config(*, groq_configured: bool = False, gemini_configured: bool = False) -> Config:
    return Config(
        gemini_api_key="a-real-looking-gemini-key" if gemini_configured else None,
        gemini_model="gemini-flash-latest",
        reddit_client_id=None,
        reddit_client_secret=None,
        reddit_user_agent="test-agent",
        groq_api_key="a-real-looking-groq-key" if groq_configured else None,
    )


def _mock_completion(text: str):
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=text))]
    return response


def _status_error(cls, status_code: int):
    return cls(f"simulated {status_code}", response=MagicMock(status_code=status_code), body=None)


# --- GroqProvider.generate_text --------------------------------------------------


def test_groq_returns_valid_response():
    with patch("src.ai.groq_provider.Groq") as mock_client_cls:
        mock_client_cls.return_value.chat.completions.create.return_value = _mock_completion("hello from groq")
        result = GroqProvider(_config(groq_configured=True)).generate_text("a prompt")

    assert result == "hello from groq"


def test_groq_invalid_key():
    with patch("src.ai.groq_provider.Groq") as mock_client_cls:
        mock_client_cls.return_value.chat.completions.create.side_effect = _status_error(
            groq.AuthenticationError, 401
        )
        with pytest.raises(AIProviderAuthError):
            GroqProvider(_config(groq_configured=True)).generate_text("a prompt")


def test_groq_rate_limit():
    with patch("src.ai.groq_provider.Groq") as mock_client_cls:
        mock_client_cls.return_value.chat.completions.create.side_effect = _status_error(groq.RateLimitError, 429)
        with pytest.raises(AIProviderRateLimitError):
            GroqProvider(_config(groq_configured=True)).generate_text("a prompt")


def test_groq_other_error_status_raises_generic_provider_error():
    with patch("src.ai.groq_provider.Groq") as mock_client_cls:
        mock_client_cls.return_value.chat.completions.create.side_effect = _status_error(
            groq.BadRequestError, 400
        )
        with pytest.raises(Exception) as exc_info:
            GroqProvider(_config(groq_configured=True)).generate_text("a prompt")

    assert "400" in str(exc_info.value)


def test_groq_empty_response_raises():
    with patch("src.ai.groq_provider.Groq") as mock_client_cls:
        mock_client_cls.return_value.chat.completions.create.return_value = _mock_completion("")
        with pytest.raises(Exception):
            GroqProvider(_config(groq_configured=True)).generate_text("a prompt")


def test_groq_check_connection_never_raises_on_success():
    with patch("src.ai.groq_provider.Groq") as mock_client_cls:
        mock_client_cls.return_value.models.list.return_value.data = []
        GroqProvider(_config(groq_configured=True)).check_connection()  # must not raise


# --- get_ai_provider factory priority: Groq -> Gemini -> Mock --------------------


def test_factory_selects_groq_when_key_present():
    provider = get_ai_provider(_config(groq_configured=True, gemini_configured=True))
    assert isinstance(provider, GroqProvider)


def test_factory_falls_back_to_gemini():
    provider = get_ai_provider(_config(groq_configured=False, gemini_configured=True))
    assert isinstance(provider, GeminiProvider)
    assert not isinstance(provider, GroqProvider)


def test_factory_falls_back_to_mock_when_neither_configured():
    from src.ai.mock_provider import MockAIProvider

    provider = get_ai_provider(_config(groq_configured=False, gemini_configured=False))
    assert isinstance(provider, MockAIProvider)


def test_factory_force_mock_overrides_groq():
    from src.ai.mock_provider import MockAIProvider

    provider = get_ai_provider(_config(groq_configured=True), force_mock=True)
    assert isinstance(provider, MockAIProvider)
