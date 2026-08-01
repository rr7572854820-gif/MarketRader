"""Tests for src/insights/keyword_extraction.py: AI-assisted natural-
language -> GitHub search query extraction, with its deterministic
fallback. All tests use a stub AIProvider, never a real call - same
discipline as tests/test_aggregator.py, whose AI-with-fallback shape
this module mirrors.
"""

from __future__ import annotations

import pytest

from src.ai.base import AIProvider, AIProviderError
from src.insights.keyword_extraction import extract_search_terms


class _FixedResponseProvider(AIProvider):
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    def check_connection(self) -> None:
        return

    def generate_text(self, prompt: str) -> str:
        self.calls += 1
        return self.response


class _ErrorProvider(AIProvider):
    def check_connection(self) -> None:
        return

    def generate_text(self, prompt: str) -> str:
        raise AIProviderError("simulated keyword-extraction failure")


# --- AI path ------------------------------------------------------------------------


def test_extract_returns_short_keywords():
    provider = _FixedResponseProvider("invoicing automation")
    result = extract_search_terms("problems with invoice automation", provider)

    assert len(result.split()) <= 3
    assert result == "invoicing automation"
    assert provider.calls == 1


def test_extract_uses_first_line_when_model_returns_multiple_candidates():
    """Real-world regression case: a live Groq call for this exact
    prompt returned multiple newline-separated candidate phrases
    despite being told to return only one - confirmed by a real call
    before this fallback was written, not assumed. The first line was
    consistently the intended answer.
    """
    provider = _FixedResponseProvider("invoice automation\ninvoicing\npayment automation")
    result = extract_search_terms("problems with invoice automation", provider)

    assert result == "invoice automation"


def test_extract_strips_punctuation_and_quotes():
    provider = _FixedResponseProvider('"saas, productivity."')
    result = extract_search_terms("best saas ideas", provider)

    assert result == "saas productivity"


def test_extract_caps_at_three_words_even_if_model_ignores_the_limit():
    provider = _FixedResponseProvider("one two three four five")
    result = extract_search_terms("some rambling input", provider)

    assert result.split() == ["one", "two", "three"]


# --- Fallback path --------------------------------------------------------------------


def test_extract_falls_back_on_ai_failure():
    provider = _ErrorProvider()

    result = extract_search_terms("problems with invoice automation", provider)  # must not raise

    assert result
    assert len(result.split()) <= 3


def test_extract_fallback_prefers_meaningful_words_over_stopwords():
    provider = _ErrorProvider()

    result = extract_search_terms("I want to build something for invoice automation", provider)

    assert "invoice" in result.split()
    assert "want" not in result.split()


def test_extract_fallback_never_returns_blank_even_for_all_stopword_input():
    provider = _ErrorProvider()

    result = extract_search_terms("what is up with it", provider)

    assert result.strip() != ""


def test_extract_falls_back_when_ai_returns_empty_response():
    provider = _FixedResponseProvider("   ")
    result = extract_search_terms("problems with invoice automation", provider)

    assert result.strip() != ""
    assert "invoice" in result.split()


@pytest.mark.parametrize("bad_response", ["Keywords:", "keyword: saas tools", "```\nsaas tools\n```"])
def test_extract_handles_awkward_model_formatting(bad_response: str):
    provider = _FixedResponseProvider(bad_response)
    result = extract_search_terms("best saas ideas", provider)

    assert result.strip() != ""
