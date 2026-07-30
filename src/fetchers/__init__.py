"""Fetcher factory — the only place that decides which concrete Fetcher
implementation to use.

Everything else in the project must call get_fetcher(config) and depend
only on Fetcher / FetcherError / src.models.FetchedPost — never import
RedditFetcher or MockFetcher directly. That indirection is what lets a
future source (Hacker News, Product Hunt, GitHub Issues) be added by
adding one class and one branch here, with zero changes anywhere else.
"""

from __future__ import annotations

from src.config import Config
from src.fetchers.base import Fetcher, FetcherError
from src.fetchers.mock_fetcher import MockFetcher
from src.fetchers.reddit_fetcher import RedditFetcher

__all__ = ["Fetcher", "FetcherError", "get_fetcher"]


def get_fetcher(config: Config) -> Fetcher:
    """Return the Fetcher appropriate for the current configuration.

    Real Reddit access is used only when config.reddit_configured is
    True; a MockFetcher is returned automatically otherwise. No code
    change is needed to switch — set or unset REDDIT_CLIENT_ID /
    REDDIT_CLIENT_SECRET in .env.
    """
    if config.reddit_configured:
        return RedditFetcher(config)
    return MockFetcher()
