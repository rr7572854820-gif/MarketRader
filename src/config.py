"""Loads and validates environment variables. No other module should read
os.environ directly — go through load_config() so there's exactly one place
that knows the required variable names and exactly one place that could leak
a secret if someone got careless with a print statement.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_CLAUDE_MODEL = "claude-sonnet-5"


class ConfigError(Exception):
    """Raised when required configuration is missing or empty."""


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


@dataclass(frozen=True)
class Config:
    reddit_client_id: str
    reddit_client_secret: str
    reddit_user_agent: str
    anthropic_api_key: str
    claude_model: str


def load_config() -> Config:
    """Loads .env (if present) and returns a validated Config.

    Raises ConfigError, with a message naming which variable is missing,
    if anything required is absent. Never returns partial/default secrets.
    """
    load_dotenv()  # no-op if .env doesn't exist — safe to call unconditionally

    return Config(
        reddit_client_id=_require("REDDIT_CLIENT_ID"),
        reddit_client_secret=_require("REDDIT_CLIENT_SECRET"),
        reddit_user_agent=_require("REDDIT_USER_AGENT"),
        anthropic_api_key=_require("ANTHROPIC_API_KEY"),
        claude_model=os.environ.get("CLAUDE_MODEL") or DEFAULT_CLAUDE_MODEL,
    )
