"""Task 1 connection check.

Verifies that Reddit (read-only) and Claude API credentials actually work,
before any fetching/extraction code depends on them. Deliberately does
nothing else: no fetching, no extraction, no report output.

Run from the project root:
    python -m src.check_connections

Secrets policy: this script never prints a credential value, and only
prints an exception's type name — not its message or args — since library
exceptions can echo back request details we don't want to risk exposing.
"""

from __future__ import annotations

import sys

from src.config import Config, ConfigError, load_config


def check_reddit(config: Config) -> bool:
    import praw
    import prawcore

    try:
        reddit = praw.Reddit(
            client_id=config.reddit_client_id,
            client_secret=config.reddit_client_secret,
            user_agent=config.reddit_user_agent,
        )
        reddit.read_only = True
        # Constructing the client above never actually contacts Reddit —
        # only this call does, so this is the real credential check.
        _ = reddit.subreddit("announcements").display_name
    except (prawcore.exceptions.OAuthException, prawcore.exceptions.ResponseException):
        print("[FAIL] Reddit authentication failed — check REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET.")
        return False
    except Exception as exc:
        print(f"[FAIL] Reddit check failed unexpectedly ({type(exc).__name__}).")
        return False
    else:
        print("[OK]   Reddit authentication succeeded (read-only).")
        return True


def check_claude(config: Config) -> bool:
    import anthropic

    try:
        client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        # Listing models confirms the key works without spending on a
        # completion — this call is free.
        client.models.list(limit=1)
    except anthropic.AuthenticationError:
        print("[FAIL] Claude authentication failed — check ANTHROPIC_API_KEY.")
        return False
    except Exception as exc:
        print(f"[FAIL] Claude check failed unexpectedly ({type(exc).__name__}).")
        return False
    else:
        print("[OK]   Claude API authentication succeeded.")
        return True


def main() -> int:
    print("MarketRadar — Connection Check\n")

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"[FAIL] {exc}")
        return 1

    reddit_ok = check_reddit(config)
    claude_ok = check_claude(config)

    print()
    if reddit_ok and claude_ok:
        print("All connections verified. Ready for Task 2.")
        return 0

    print("One or more connections failed. Fix the issue(s) above and re-run before continuing.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
