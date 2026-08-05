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
from src.fetchers.github_fetcher import GitHubFetcher
from src.fetchers.hn_fetcher import HNFetcher
from src.fetchers.mock_fetcher import MockFetcher
from src.fetchers.reddit_fetcher import RedditFetcher

__all__ = ["Fetcher", "FetcherError", "get_fetcher"]


def get_fetcher(config: Config, *, source: str = "reddit", force_mock: bool = False) -> Fetcher:
    """Return the Fetcher appropriate for the requested source.

    Real Reddit access is used only when source="reddit" (the default,
    unchanged from before GitHub existed) and config.reddit_configured
    is True; a MockFetcher is returned automatically otherwise. No code
    change is needed to switch Reddit on/off — set or unset
    REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET in .env.

    source="github" always returns a real GitHubFetcher (unless
    force_mock) — unlike Reddit, GitHub has no "configured" boolean to
    auto-detect, since a repo name is required query input, not a
    credential; GITHUB_TOKEN only raises its rate limit, it doesn't
    gate whether GitHubFetcher can be used at all.

    source="hackernews" (alias "hn") always returns a real HNFetcher
    (unless force_mock) — Hacker News has no "configured" boolean
    either, and no credential at all: the Algolia HN Search API is
    public and unauthenticated, so there's nothing to gate on.

    Args:
        source: Which real source to use when not falling back to mock
            — "reddit" (default), "github", or "hackernews"/"hn".
            Wiring this into the CLI for GitHub/Hacker News is a
            separate, later task.
        force_mock: If True, always returns MockFetcher regardless of
            config or source — e.g. for a CLI --mock flag (see
            src/pipeline/). This is the sanctioned way to force mock
            mode; still never construct MockFetcher directly outside
            this factory.
    """
    if force_mock:
        return MockFetcher()
    if source == "github":
        return GitHubFetcher(config)
    if source in ("hackernews", "hn"):
        return HNFetcher(config)
    if config.reddit_configured:
        return RedditFetcher(config)
    return MockFetcher()
