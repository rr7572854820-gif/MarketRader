"""Tests for src/pipeline/.

Every Pipeline constructed here explicitly sets ai_provider="mock" (and
usually force_mock_fetch=True too) — the real .env in this project has
a real GEMINI_API_KEY configured, and ai_provider="auto" would silently
make real, billed API calls during what's supposed to be a fast,
offline test suite. This is deliberate test hygiene, not incidental.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pytest

from src.ai import get_ai_provider
from src.ai.base import AIProvider
from src.ai.gemini_provider import GeminiProvider
from src.ai.mock_provider import MockAIProvider
from src.config import Config
from src.fetchers import get_fetcher
from src.fetchers.base import Fetcher, FetcherError
from src.fetchers.mock_fetcher import MockFetcher
from src.fetchers.reddit_fetcher import RedditFetcher
from src.models import FetchedPost, FetchQuery
from src.pipeline.pipeline import Pipeline, PipelineConfig, _CountingAIProvider, _fetch_with_retry


def make_config(reddit_configured: bool = False, gemini_configured: bool = False) -> Config:
    return Config(
        gemini_api_key=("fake-key" if gemini_configured else None),
        gemini_model="gemini-flash-latest",
        reddit_client_id=("fake-id" if reddit_configured else None),
        reddit_client_secret=("fake-secret" if reddit_configured else None),
        reddit_user_agent="test-agent",
    )


# --- force_mock overrides on the factories ---------------------------------


def test_force_mock_fetch_overrides_real_reddit_config():
    config = make_config(reddit_configured=True)
    assert config.reddit_configured is True  # sanity: would normally pick RedditFetcher

    fetcher = get_fetcher(config, force_mock=True)
    assert isinstance(fetcher, MockFetcher)
    assert not isinstance(fetcher, RedditFetcher)


def test_without_force_mock_real_reddit_config_still_used():
    config = make_config(reddit_configured=True)
    fetcher = get_fetcher(config, force_mock=False)
    assert isinstance(fetcher, RedditFetcher)


def test_force_mock_ai_overrides_real_gemini_config():
    config = make_config(gemini_configured=True)
    provider = get_ai_provider(config, force_mock=True)
    assert isinstance(provider, MockAIProvider)
    assert not isinstance(provider, GeminiProvider)


# --- _CountingAIProvider -----------------------------------------------------


class _StubAIProvider(AIProvider):
    def check_connection(self) -> None:
        return

    def generate_text(self, prompt: str) -> str:
        return f"response to: {prompt}"


def test_counting_provider_counts_generate_text_calls():
    counting = _CountingAIProvider(_StubAIProvider())
    assert counting.call_count == 0

    counting.generate_text("a")
    counting.generate_text("b")
    counting.generate_text("c")

    assert counting.call_count == 3


def test_counting_provider_passes_through_response():
    counting = _CountingAIProvider(_StubAIProvider())
    assert counting.generate_text("hello") == "response to: hello"


# --- fetch retry -------------------------------------------------------------


class _AlwaysFailsFetcher(Fetcher):
    def __init__(self) -> None:
        self.attempts = 0

    def fetch(self, query: FetchQuery) -> List[FetchedPost]:
        self.attempts += 1
        raise FetcherError("simulated transient failure")


class _FailsTwiceThenSucceedsFetcher(Fetcher):
    def __init__(self) -> None:
        self.attempts = 0

    def fetch(self, query: FetchQuery) -> List[FetchedPost]:
        self.attempts += 1
        if self.attempts < 3:
            raise FetcherError("simulated transient failure")
        return []


def test_fetch_retry_gives_up_after_max_attempts():
    fetcher = _AlwaysFailsFetcher()
    with pytest.raises(FetcherError):
        _fetch_with_retry(fetcher, FetchQuery(community="x"))
    assert fetcher.attempts == 3  # _FETCH_MAX_ATTEMPTS


def test_fetch_retry_succeeds_after_transient_failures():
    fetcher = _FailsTwiceThenSucceedsFetcher()
    result = _fetch_with_retry(fetcher, FetchQuery(community="x"))
    assert result == []
    assert fetcher.attempts == 3


# --- full pipeline runs, fully offline ---------------------------------------


def test_full_pipeline_offline_mock_never_raises_and_produces_summary(tmp_path: Path):
    """MockAIProvider returns schema-valid JSON (with real, verbatim
    quotes pulled from each post's own text), so every extraction now
    succeeds in one call with no retry, and clustering runs the real
    AI-assisted path rather than falling back to lexical overlap. The
    pipeline must still complete, still save a report and a summary,
    and still report succeeded=True.

    cache_path is isolated to tmp_path: valid mock JSON is now
    cacheable (unlike before this fix), so without isolation this test
    would read/write the project's real, persistent .cache/ file (see
    PipelineConfig.cache_path's repo-relative default) and its
    ai_calls_made assertion would depend on prior test runs.
    """
    config = PipelineConfig(
        subreddit="test",
        post_limit=3,
        output_dir=tmp_path,
        ai_provider="mock",
        force_mock_fetch=True,
        cache_path=tmp_path / "ai_cache.json",
    )

    result = Pipeline(config).run()

    assert result.summary.succeeded is True
    assert result.summary.posts_fetched == 3
    assert result.summary.posts_analyzed == 3  # every extraction succeeds against valid mock JSON
    # One extraction call per post (no retry needed) + one clustering call.
    assert result.summary.ai_calls_made == 4
    assert len(result.summary.errors) == 0
    assert result.summary.report_path is not None
    assert result.summary.report_path.exists()
    assert result.report is not None


def test_pipeline_saves_valid_execution_summary_json(tmp_path: Path):
    config = PipelineConfig(
        subreddit="test", post_limit=2, output_dir=tmp_path, ai_provider="mock", force_mock_fetch=True
    )

    Pipeline(config).run()

    summary_files = list(tmp_path.glob("pipeline_run_*.json"))
    assert len(summary_files) == 1
    data = json.loads(summary_files[0].read_text(encoding="utf-8"))
    assert data["posts_fetched"] == 2
    assert data["succeeded"] is True
    assert "start_time" in data and "end_time" in data and "duration_seconds" in data


def test_pipeline_report_format_terminal_only_does_not_save_markdown(tmp_path: Path):
    config = PipelineConfig(
        subreddit="test",
        post_limit=1,
        output_dir=tmp_path,
        ai_provider="mock",
        force_mock_fetch=True,
        report_format="terminal",
    )

    result = Pipeline(config).run()

    assert result.summary.report_path is None
    assert not list(tmp_path.glob("report_*.md"))


def test_pipeline_never_raises_on_unexpected_internal_failure(tmp_path: Path, monkeypatch):
    """The one deliberate broad except in this codebase — confirm it
    actually catches an arbitrary unexpected exception rather than
    letting it propagate, and records it honestly as a failure.
    """
    import src.pipeline.pipeline as pipeline_module

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated unexpected bug")

    monkeypatch.setattr(pipeline_module, "generate_report", _boom)

    config = PipelineConfig(
        subreddit="test", post_limit=1, output_dir=tmp_path, ai_provider="mock", force_mock_fetch=True
    )

    result = Pipeline(config).run()  # must not raise

    assert result.summary.succeeded is False
    assert any("simulated unexpected bug" in e for e in result.summary.errors)
    assert result.report is None


# --- CLI ----------------------------------------------------------------------


def test_cli_mock_flag_runs_fully_offline_end_to_end(tmp_path: Path):
    from src.pipeline.runner import main

    exit_code = main(["--mock", "--limit", "2", "--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert list(tmp_path.glob("report_*.md"))
    assert list(tmp_path.glob("pipeline_run_*.json"))


# --- Task 7: CLI validation ---------------------------------------------------


@pytest.mark.parametrize("bad_limit", ["0", "-5", "abc", "3.5"])
def test_cli_rejects_invalid_limit_with_clean_error(bad_limit: str, capsys):
    from src.pipeline.runner import main

    with pytest.raises(SystemExit) as exc_info:
        main(["--mock", "--limit", bad_limit])

    assert exc_info.value.code == 2  # argparse's standard "bad usage" exit code
    captured = capsys.readouterr()
    assert "--limit" in captured.err


def test_cli_rejects_blank_subreddit_with_clean_error(capsys):
    from src.pipeline.runner import main

    with pytest.raises(SystemExit) as exc_info:
        main(["--mock", "--subreddit", "   "])

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "--subreddit" in captured.err


def test_cli_accepts_valid_positive_limit():
    from src.pipeline.runner import _positive_int

    assert _positive_int("1") == 1
    assert _positive_int("25") == 25


def test_cli_help_exits_zero_and_lists_all_flags(capsys):
    from src.pipeline.runner import main

    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    for flag in ["--subreddit", "--keyword", "--limit", "--output-dir", "--ai-provider", "--format", "--mock", "--verbose"]:
        assert flag in captured.out


# --- Task 7: logging configuration --------------------------------------------


def test_configure_logging_default_suppresses_third_party_but_shows_our_own():
    import logging

    from src.pipeline.runner import _configure_logging

    _configure_logging(verbose=False)

    assert logging.getLogger().getEffectiveLevel() == logging.WARNING  # third-party stays quiet
    assert logging.getLogger("src").getEffectiveLevel() == logging.INFO  # our own logs show


def test_configure_logging_verbose_shows_everything():
    import logging

    from src.pipeline.runner import _configure_logging

    _configure_logging(verbose=True)

    assert logging.getLogger().getEffectiveLevel() == logging.DEBUG
    assert logging.getLogger("src").getEffectiveLevel() == logging.DEBUG
