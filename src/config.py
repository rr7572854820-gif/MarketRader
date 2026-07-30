"""Loads and validates environment variables. No other module should read
os.environ directly — go through load_config() so there's exactly one place
that knows the required variable names and exactly one place that could leak
a secret if someone got careless with a print statement.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
MOCK_USER_AGENT = "marketradar-mock-mode (no real Reddit credentials configured)"

# .env is loaded from this fixed path — the project root, i.e. the
# directory containing src/ — rather than relying on python-dotenv's
# implicit upward search from the current working directory. Confirmed
# by testing directly (Task 7) that the implicit search silently fails
# to find .env when a command is invoked from outside the project root:
# every value falls back to "unconfigured" with no error at all, which
# is exactly the kind of unpredictable-between-invocations behavior
# this project's config loading should never have. This makes .env
# discovery depend only on where the project lives on disk, never on
# which directory a command happens to be run from.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DOTENV_PATH = _PROJECT_ROOT / ".env"


def _env_str(name: str) -> Optional[str]:
    """Reads an env var and returns it, or None if unset OR blank.

    Whitespace-only values (e.g. a stray "GEMINI_API_KEY=   " left over
    from editing .env) are treated as unset rather than as a truthy-but-
    useless string — found by inspection (Task 7) that the original
    truthiness check would have treated "   " as "configured."
    """
    value = os.environ.get(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


@dataclass(frozen=True)
class Config:
    # Both Reddit and Gemini are optional at the config-loading level —
    # nothing here can fail to load. Each consumer decides what it
    # actually needs (e.g. the Fetcher needs neither an AI key nor real
    # Reddit creds to run in mock mode; check_connections.py wants both
    # reported clearly) and checks the relevant *_configured property
    # itself, rather than the whole project failing to start because one
    # unrelated credential is missing.
    gemini_api_key: Optional[str]
    gemini_model: str
    reddit_client_id: Optional[str]
    reddit_client_secret: Optional[str]
    reddit_user_agent: str

    @property
    def reddit_configured(self) -> bool:
        """True only when real Reddit credentials are present."""
        return bool(self.reddit_client_id and self.reddit_client_secret)

    @property
    def gemini_configured(self) -> bool:
        """True only when a Gemini API key is present."""
        return bool(self.gemini_api_key)


def load_config(dotenv_path: Optional[Path] = None) -> Config:
    """Loads .env (if present) and returns a Config.

    Always succeeds — loading configuration and requiring a particular
    value to be present are different concerns. Whichever code path
    actually needs Reddit or Gemini checks Config.reddit_configured /
    Config.gemini_configured and fails loudly itself, with a message
    specific to what it was trying to do.

    By default .env is read from the project root (see _DOTENV_PATH),
    so this behaves identically regardless of the current working
    directory a command is invoked from. Pass dotenv_path explicitly
    only for test isolation from the real .env (see tests/test_config.py)
    — no production code path should ever need to override this.
    """
    load_dotenv(dotenv_path=dotenv_path or _DOTENV_PATH)  # no-op if the file doesn't exist — safe to call unconditionally

    return Config(
        gemini_api_key=_env_str("GEMINI_API_KEY"),
        gemini_model=_env_str("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL,
        reddit_client_id=_env_str("REDDIT_CLIENT_ID"),
        reddit_client_secret=_env_str("REDDIT_CLIENT_SECRET"),
        reddit_user_agent=_env_str("REDDIT_USER_AGENT") or MOCK_USER_AGENT,
    )
