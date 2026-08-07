"""Tests for src/search/query_expander.py. Stub AIProvider throughout
(same pattern as tests/test_aggregator.py, tests/test_extractor.py) -
never a real AI call.

test_pipeline_uses_expander lives here (rather than tests/test_pipeline.py)
because the task that added it named this file explicitly - it exercises
Pipeline.run()'s wiring of QueryExpander, not QueryExpander in isolation,
so it needs Pipeline/PipelineConfig/Fetcher imports too.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from src.ai.base import AIProvider, AIProviderError
from src.fetchers.base import Fetcher
from src.models import FetchedPost, FetchQuery
from src.pipeline.pipeline import Pipeline, PipelineConfig
from src.search.query_expander import QueryExpander


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
        raise AIProviderError("simulated provider failure")


def test_expand_returns_list():
    provider = _FixedResponseProvider(json.dumps(["invoicing saas", "billing tool", "accounts receivable"]))
    result = QueryExpander(provider).expand("invoicing small business")

    assert isinstance(result, list)
    assert len(result) >= 1


def test_expand_returns_max_terms():
    provider = _FixedResponseProvider(
        json.dumps(["term one", "term two", "term three", "term four", "term five", "term six"])
    )
    result = QueryExpander(provider).expand("some query", max_terms=4)

    assert len(result) <= 4


def test_expand_fallback_on_ai_failure():
    provider = _ErrorProvider()

    result = QueryExpander(provider).expand("invoicing small business")  # must not raise

    assert result == ["invoicing small business"]


def test_expand_fallback_on_invalid_json():
    provider = _FixedResponseProvider("not json")

    result = QueryExpander(provider).expand("invoicing small business")  # must not raise

    assert result == ["invoicing small business"]


def test_expand_fallback_on_empty_list():
    provider = _FixedResponseProvider("[]")

    result = QueryExpander(provider).expand("invoicing small business")

    assert result == ["invoicing small business"]


def test_expand_filters_short_terms():
    provider = _FixedResponseProvider(json.dumps(["a", "ab", "valid term"]))

    result = QueryExpander(provider).expand("some query")

    assert "a" not in result
    assert "ab" not in result
    assert "valid term" in result


def test_expand_returns_8_terms():
    """_DEFAULT_MAX_TERMS is now 8 (raised from 3 - see this module's
    own comment on why, including the confirmed GitHub/Groq rate-limit
    tradeoff). Zero-cost/zero-network per ENGINEERING_GUIDE.md - a
    canned, well-formed response stands in for what a real provider
    following the new prompt should return, not a live call.
    """
    provider = _FixedResponseProvider(
        json.dumps(
            [
                "stripe checkout",
                "payment gateway timeout",
                "billing subscription saas",
                "invoice generation",
                "paypal integration",
                "refund processing",
                "credit card declined",
                "checkout flow",
            ]
        )
    )
    result = QueryExpander(provider).expand("payments")

    assert len(result) == 8


def test_expand_no_generic_words():
    provider = _FixedResponseProvider(
        json.dumps(
            [
                "stripe checkout",
                "payment gateway timeout",
                "billing subscription saas",
                "invoice generation",
                "paypal integration",
                "refund processing",
                "credit card declined",
                "checkout flow",
            ]
        )
    )
    result = QueryExpander(provider).expand("payments")

    generic_words = {"best", "ideas", "problems", "tool"}
    for term in result:
        term_words = set(term.lower().split())
        assert not (term_words & generic_words), f"{term!r} contains a generic word"


def test_expand_specific_products():
    provider = _FixedResponseProvider(
        json.dumps(
            [
                "stripe checkout",
                "payment gateway timeout",
                "billing subscription saas",
                "invoice generation",
                "paypal integration",
                "refund processing",
                "credit card declined",
                "checkout flow",
            ]
        )
    )
    result = QueryExpander(provider).expand("payments")

    joined = " ".join(result).lower()
    assert any(product in joined for product in ("stripe", "paypal", "billing", "checkout"))


def test_pipeline_uses_expander(tmp_path: Path, monkeypatch, caplog):
    """Pipeline.run() must call QueryExpander.expand(), log the
    expansion, and pass its first returned term - not the raw
    keyword - to the fetcher. See pipeline.py's own comment at its
    QueryExpander call site for why only the first term is used.
    """
    import src.pipeline.pipeline as pipeline_module

    captured: dict = {}

    class _StubExpander:
        def __init__(self, ai_provider) -> None:
            pass

        def expand(self, user_input: str) -> List[str]:
            captured["expand_called_with"] = user_input
            return ["invoicing saas", "billing tool"]

    class _StubFetcher(Fetcher):
        def fetch(self, query: FetchQuery) -> List[FetchedPost]:
            captured["fetch_keyword"] = query.keyword
            return []

    monkeypatch.setattr(pipeline_module, "QueryExpander", _StubExpander)
    monkeypatch.setattr(
        pipeline_module, "get_fetcher", lambda config, *, source="reddit", force_mock=False: _StubFetcher()
    )

    config = PipelineConfig(
        source="github",
        keyword="invoicing small business",
        post_limit=5,
        output_dir=tmp_path,
        ai_provider="mock",
        cache_path=tmp_path / "ai_cache.json",
    )

    with caplog.at_level(logging.INFO, logger=pipeline_module.__name__):
        Pipeline(config).run()

    assert captured["expand_called_with"] == "invoicing small business"
    assert captured["fetch_keyword"] == "invoicing saas"  # first expanded term
    assert any("expand" in record.message.lower() for record in caplog.records)
