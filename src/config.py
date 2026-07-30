"""Loads and validates environment variables. No other module should read
os.environ directly — go through load_config() so there's exactly one place
that knows the required variable names and exactly one place that could leak
a secret if someone got careless with a print statement.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
MOCK_USER_AGENT = "marketradar-mock-mode (no real Reddit credentials configured)"


def _optional(name: str) -> Optional[str]:
    value = os.environ.get(name)
    return value if value else None


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


def load_config() -> Config:
    """Loads .env (if present) and returns a Config.

    Always succeeds — loading configuration and requiring a particular
    value to be present are different concerns. Whichever code path
    actually needs Reddit or Gemini checks Config.reddit_configured /
    Config.gemini_configured and fails loudly itself, with a message
    specific to what it was trying to do.
    """
    load_dotenv()  # no-op if .env doesn't exist — safe to call unconditionally

    return Config(
        gemini_api_key=_optional("GEMINI_API_KEY"),
        gemini_model=os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL,
        reddit_client_id=_optional("REDDIT_CLIENT_ID"),
        reddit_client_secret=_optional("REDDIT_CLIENT_SECRET"),
        reddit_user_agent=os.environ.get("REDDIT_USER_AGENT") or MOCK_USER_AGENT,
    )
