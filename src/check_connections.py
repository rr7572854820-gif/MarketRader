"""Task 1 connection check.

Verifies that the configured AI provider (Gemini) and, optionally,
Reddit credentials actually work. Reddit is optional: if
REDDIT_CLIENT_ID/SECRET aren't set, Reddit is skipped rather than
treated as a failure — no Reddit account or API key is required to use
this project. Deliberately does nothing else: no fetching, no
extraction, no report output.

The AI provider is checked through the AIProvider abstraction
(src/ai/) — this file never imports google.genai (or any other
provider's SDK) directly, so swapping the provider later requires no
change here.

Run from the project root:
    python -m src.check_connections

Secrets policy: this script never prints a credential value, and only
prints an exception's type name — not its message or args — since
library exceptions can echo back request details we don't want to risk
exposing.
"""

from __future__ import annotations

import sys

from src.ai import AIProviderError, get_ai_provider
from src.config import Config, load_config


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
        print("[FAIL] Reddit authentication failed - check REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET.")
        return False
    except Exception as exc:
        print(f"[FAIL] Reddit check failed unexpectedly ({type(exc).__name__}).")
        return False
    else:
        print("[OK]   Reddit authentication succeeded (read-only).")
        return True


def check_ai_provider(config: Config) -> bool:
    try:
        get_ai_provider(config).check_connection()
    except AIProviderError as exc:
        print(f"[FAIL] Gemini check failed: {exc}")
        return False
    else:
        print("[OK]   Gemini authentication succeeded.")
        return True


def main() -> int:
    print("MarketRadar - Connection Check\n")

    config = load_config()

    if config.reddit_configured:
        reddit_ok = check_reddit(config)
    else:
        print("[SKIP] Reddit not configured - running in mock mode (no account/API key needed).")
        print("       Add REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET to .env later to switch to real Reddit data.")
        reddit_ok = True

    if config.gemini_configured:
        ai_ok = check_ai_provider(config)
    else:
        print("[FAIL] Gemini not configured - set GEMINI_API_KEY in .env (this one is required).")
        ai_ok = False

    print()
    if reddit_ok and ai_ok:
        print("Ready for Task 3." + ("" if config.reddit_configured else " (Reddit will use mock data.)"))
        return 0

    print("One or more connections failed. Fix the issue(s) above and re-run before continuing.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
