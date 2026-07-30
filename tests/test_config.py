"""Tests for src/config.py.

Every test here explicitly isolates from the real .env (which has real
secrets in it) two ways: monkeypatch.delenv clears anything already in
the process environment, and dotenv_path points at a controlled,
temporary location instead of the project's real .env. Without both,
these tests would either leak real config into assertions or have
load_dotenv() silently repopulate "cleared" variables from the real
file — see load_config()'s docstring for why dotenv_path exists at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import DEFAULT_GEMINI_MODEL, MOCK_USER_AGENT, load_config

_ENV_KEYS = ["GEMINI_API_KEY", "GEMINI_MODEL", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"]


@pytest.fixture(autouse=True)
def _clear_real_env(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_defaults_when_nothing_configured(tmp_path: Path):
    missing_dotenv = tmp_path / ".env"  # deliberately does not exist

    config = load_config(dotenv_path=missing_dotenv)

    assert config.gemini_api_key is None
    assert config.gemini_configured is False
    assert config.gemini_model == DEFAULT_GEMINI_MODEL
    assert config.reddit_client_id is None
    assert config.reddit_client_secret is None
    assert config.reddit_configured is False
    assert config.reddit_user_agent == MOCK_USER_AGENT


def test_reads_real_values_from_a_dotenv_file(tmp_path: Path):
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text(
        "GEMINI_API_KEY=test-key-123\n"
        "GEMINI_MODEL=gemini-test-model\n"
        "REDDIT_CLIENT_ID=id-123\n"
        "REDDIT_CLIENT_SECRET=secret-456\n"
        "REDDIT_USER_AGENT=my-test-agent\n",
        encoding="utf-8",
    )

    config = load_config(dotenv_path=dotenv_file)

    assert config.gemini_api_key == "test-key-123"
    assert config.gemini_configured is True
    assert config.gemini_model == "gemini-test-model"
    assert config.reddit_client_id == "id-123"
    assert config.reddit_client_secret == "secret-456"
    assert config.reddit_configured is True
    assert config.reddit_user_agent == "my-test-agent"


def test_whitespace_only_values_are_treated_as_unset(tmp_path: Path):
    """A stray "GEMINI_API_KEY=   " (blank after edits) must not be
    treated as a real, usable key — found by inspection in Task 7.
    """
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text('GEMINI_API_KEY="   "\n', encoding="utf-8")

    config = load_config(dotenv_path=dotenv_file)

    assert config.gemini_api_key is None
    assert config.gemini_configured is False


def test_partial_reddit_credentials_not_considered_configured(tmp_path: Path):
    """Only a client_id with no client_secret must not count as
    reddit_configured — both are required together.
    """
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text("REDDIT_CLIENT_ID=id-only\n", encoding="utf-8")

    config = load_config(dotenv_path=dotenv_file)

    assert config.reddit_client_id == "id-only"
    assert config.reddit_client_secret is None
    assert config.reddit_configured is False


def test_missing_dotenv_file_does_not_raise(tmp_path: Path):
    """load_config() must always succeed, per its own contract — a
    missing .env is not an error, just "nothing configured."
    """
    config = load_config(dotenv_path=tmp_path / "does_not_exist.env")
    assert config.gemini_configured is False
    assert config.reddit_configured is False


def test_config_loading_is_independent_of_current_working_directory(tmp_path: Path, monkeypatch):
    """The real bug this test guards against (Task 7): before the fix,
    load_config() relied on python-dotenv's implicit upward search from
    the process's current working directory, which silently found
    nothing when invoked from outside the project root. Explicitly
    passing dotenv_path sidesteps cwd entirely — this test proves that
    behavior no longer depends on cwd at all when a path is given.
    """
    dotenv_file = tmp_path / "somewhere" / ".env"
    dotenv_file.parent.mkdir(parents=True)
    dotenv_file.write_text("GEMINI_API_KEY=cwd-independent-key\n", encoding="utf-8")

    other_dir = tmp_path / "a" / "totally" / "different" / "cwd"
    other_dir.mkdir(parents=True)
    monkeypatch.chdir(other_dir)

    config = load_config(dotenv_path=dotenv_file)

    assert config.gemini_api_key == "cwd-independent-key"
