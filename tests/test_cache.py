"""Tests for src/pipeline/cache.py, plus a full-pipeline integration
test proving cache hits skip real AI calls end to end.

Like tests/test_pipeline.py, every Pipeline constructed here explicitly
avoids ai_provider="auto" (the real .env has a real GEMINI_API_KEY) —
either ai_provider="mock" for pipeline-level plumbing tests, or a
monkeypatched stub provider for the cache-specific integration test,
which needs a response that actually looks like valid JSON (unlike
MockAIProvider's fixed placeholder text, which is deliberately never
valid JSON and therefore never cacheable — see extractor tests).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ai.base import AIProvider
from src.pipeline.cache import CachingAIProvider, ResponseCache, hash_prompt
from src.pipeline.pipeline import Pipeline, PipelineConfig


# --- hash_prompt --------------------------------------------------------------


def test_hash_prompt_is_deterministic_and_distinguishes_content():
    assert hash_prompt("hello") == hash_prompt("hello")
    assert hash_prompt("hello") != hash_prompt("hello!")


# --- ResponseCache --------------------------------------------------------------


def test_response_cache_get_set_roundtrip(tmp_path: Path):
    cache = ResponseCache(tmp_path / "cache.json")
    assert cache.get("k1") is None

    cache.set("k1", "value one")

    assert cache.get("k1") == "value one"
    assert len(cache) == 1


def test_response_cache_persists_to_disk_and_reloads(tmp_path: Path):
    path = tmp_path / "cache.json"
    ResponseCache(path).set("k1", "persisted value")

    reloaded = ResponseCache(path)

    assert reloaded.get("k1") == "persisted value"


def test_response_cache_missing_file_starts_empty(tmp_path: Path):
    cache = ResponseCache(tmp_path / "does_not_exist.json")
    assert len(cache) == 0
    assert cache.get("anything") is None


def test_response_cache_corrupted_file_fails_open_not_raises(tmp_path: Path):
    path = tmp_path / "corrupted.json"
    path.write_text("{ this is not valid json !!!", encoding="utf-8")

    cache = ResponseCache(path)  # must not raise

    assert len(cache) == 0
    assert cache.get("anything") is None


def test_response_cache_non_dict_json_treated_as_empty(tmp_path: Path):
    path = tmp_path / "list.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    cache = ResponseCache(path)

    assert len(cache) == 0


# --- CachingAIProvider -----------------------------------------------------------


class _CountingStubProvider(AIProvider):
    """A minimal AIProvider that counts real calls and returns a fixed
    response — used to prove CachingAIProvider actually avoids calling
    the wrapped provider on a hit.
    """

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    def check_connection(self) -> None:
        return

    def generate_text(self, prompt: str) -> str:
        self.calls += 1
        return self.response


def test_caching_provider_second_identical_call_is_a_hit_and_skips_wrapped_provider(tmp_path: Path):
    stub = _CountingStubProvider('{"ok": true}')
    cache = ResponseCache(tmp_path / "cache.json")
    provider = CachingAIProvider(stub, cache)

    first = provider.generate_text("same prompt")
    second = provider.generate_text("same prompt")

    assert first == second == '{"ok": true}'
    assert stub.calls == 1  # the wrapped provider was only really called once
    assert provider.hits == 1
    assert provider.misses == 1


def test_caching_provider_different_prompts_both_miss(tmp_path: Path):
    stub = _CountingStubProvider('{"ok": true}')
    cache = ResponseCache(tmp_path / "cache.json")
    provider = CachingAIProvider(stub, cache)

    provider.generate_text("prompt A")
    provider.generate_text("prompt B")

    assert stub.calls == 2
    assert provider.misses == 2
    assert provider.hits == 0


def test_caching_provider_never_caches_malformed_json_so_retries_get_a_fresh_call(tmp_path: Path):
    """The critical retry-safety property from the approved plan:
    Extractor retries once on malformed JSON using the identical
    prompt. If a malformed response were cached, that retry would get
    the same bad response instead of a real second attempt.
    """
    stub = _CountingStubProvider("not json at all, just plain text")
    cache = ResponseCache(tmp_path / "cache.json")
    provider = CachingAIProvider(stub, cache)

    provider.generate_text("same prompt")
    provider.generate_text("same prompt")

    assert stub.calls == 2  # never cached, so both calls were real
    assert provider.misses == 2
    assert provider.hits == 0
    assert len(cache) == 0  # nothing was ever persisted


def test_caching_provider_caches_markdown_fenced_json(tmp_path: Path):
    """Extractor's own parser strips ```json fences before parsing
    (src/insights/extractor.py) — the cache's "is this JSON" check
    must recognize the same shape, or it would under-cache valid,
    fenced responses that Extractor would have accepted.
    """
    stub = _CountingStubProvider('```json\n{"ok": true}\n```')
    cache = ResponseCache(tmp_path / "cache.json")
    provider = CachingAIProvider(stub, cache)

    provider.generate_text("same prompt")
    provider.generate_text("same prompt")

    assert stub.calls == 1  # the second call was a hit


def test_caching_provider_check_connection_delegates_to_wrapped(tmp_path: Path):
    calls = []

    class _Spy(AIProvider):
        def check_connection(self) -> None:
            calls.append("checked")

        def generate_text(self, prompt: str) -> str:
            return ""

    CachingAIProvider(_Spy(), ResponseCache(tmp_path / "cache.json")).check_connection()

    assert calls == ["checked"]


# --- Full pipeline integration: cache hits really do skip real AI calls --------


def _valid_extraction_json() -> str:
    return json.dumps(
        {
            "primary_pain_point": {
                "description": "Manual reconciliation is time-consuming",
                "evidence_quote": "I run a small subscription business",
            },
            "secondary_pain_points": [],
            "user_persona": "Small business owner",
            "feature_requests": [],
            "buying_signals": [],
            "emotional_sentiment": "Frustrated",
            "urgency_score": 5,
            "opportunity_score": 50,
            "confidence": "Strong",
            "startup_opportunity": "An automation tool",
            "supporting_evidence": [],
        }
    )


class _ValidJsonStubProvider(AIProvider):
    """Returns a fixed, schema-conforming extraction JSON for every
    call, regardless of prompt content — sufficient to test caching
    end to end without spending a real Gemini call. Not meant to
    exercise Extractor's own correctness (that's test_verifier.py's
    job); the returned quote is real text from mock post-001
    specifically so Extractor's quote-verification step accepts it.
    """

    def __init__(self) -> None:
        self.calls = 0

    def check_connection(self) -> None:
        return

    def generate_text(self, prompt: str) -> str:
        self.calls += 1
        return _valid_extraction_json()


def test_pipeline_second_run_with_warm_cache_makes_zero_real_ai_calls(tmp_path: Path, monkeypatch):
    import src.pipeline.pipeline as pipeline_module

    stub = _ValidJsonStubProvider()
    monkeypatch.setattr(
        pipeline_module,
        "_resolve_ai_provider_and_label",
        lambda config, app_config: (stub, "Stub AI provider"),
    )

    cache_path = tmp_path / "ai_cache.json"
    config = PipelineConfig(
        subreddit="test",
        post_limit=1,  # exactly mock post-001, keeps the prompt set small and predictable
        output_dir=tmp_path,
        ai_provider="mock",  # irrelevant here since _resolve_ai_provider_and_label is monkeypatched
        force_mock_fetch=True,
        cache_enabled=True,
        cache_path=cache_path,
    )

    result1 = Pipeline(config).run()
    result2 = Pipeline(config).run()

    # Cold cache: one extraction call + one clustering call, both misses.
    assert result1.summary.cache_misses == 2
    assert result1.summary.cache_hits == 0
    assert result1.summary.ai_calls_made == 2

    # Warm cache: identical prompts (same post, same resulting insight
    # description feeding the same clustering prompt) both hit.
    assert result2.summary.cache_hits == 2
    assert result2.summary.cache_misses == 0
    assert result2.summary.ai_calls_made == 0  # the whole point: zero real AI calls on the second run

    assert stub.calls == 2  # the stub was truly only invoked twice total, not four times


def test_pipeline_with_cache_disabled_always_makes_fresh_calls(tmp_path: Path, monkeypatch):
    import src.pipeline.pipeline as pipeline_module

    stub = _ValidJsonStubProvider()
    monkeypatch.setattr(
        pipeline_module,
        "_resolve_ai_provider_and_label",
        lambda config, app_config: (stub, "Stub AI provider"),
    )

    config = PipelineConfig(
        subreddit="test",
        post_limit=1,
        output_dir=tmp_path,
        ai_provider="mock",
        force_mock_fetch=True,
        cache_enabled=False,
        cache_path=tmp_path / "ai_cache.json",
    )

    result1 = Pipeline(config).run()
    result2 = Pipeline(config).run()

    assert result1.summary.cache_hits == 0
    assert result1.summary.cache_misses == 0  # cache machinery isn't even constructed when disabled
    assert result2.summary.cache_hits == 0
    assert result2.summary.cache_misses == 0
    assert stub.calls == 4  # both runs always call fresh: 2 calls x 2 runs, nothing ever cached


def test_pipeline_config_defaults_to_cache_enabled():
    assert PipelineConfig().cache_enabled is True


# --- CLI wiring -----------------------------------------------------------------


def test_cli_no_cache_flag_parses_correctly():
    from src.pipeline.runner import _parse_args

    assert _parse_args(["--mock"]).no_cache is False
    assert _parse_args(["--mock", "--no-cache"]).no_cache is True


def test_cli_no_cache_end_to_end(tmp_path: Path):
    from src.pipeline.runner import main

    exit_code = main(["--mock", "--limit", "1", "--no-cache", "--output-dir", str(tmp_path)])

    assert exit_code == 0
