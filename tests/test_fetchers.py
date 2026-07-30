"""Tests for src/fetchers/mock_fetcher.py's filtering logic and the
get_fetcher factory's branching - neither had a dedicated test file
before Task 9. RedditFetcher itself is not tested here (it needs a
real network call); only that the factory returns the right type
without ever constructing a real Reddit client.
"""

from __future__ import annotations

from src.config import Config
from src.fetchers import get_fetcher
from src.fetchers.mock_fetcher import MockFetcher
from src.fetchers.reddit_fetcher import RedditFetcher
from src.models import FetchQuery


def _config(reddit_configured: bool) -> Config:
    return Config(
        gemini_api_key=None,
        gemini_model="gemini-flash-latest",
        reddit_client_id="id" if reddit_configured else None,
        reddit_client_secret="secret" if reddit_configured else None,
        reddit_user_agent="test-agent",
    )


# --- MockFetcher filtering ---------------------------------------------------------


def test_mock_fetcher_returns_all_posts_with_no_filter():
    posts = MockFetcher().fetch(FetchQuery(community="ignored", limit=100))
    assert len(posts) == 7  # the full fixed sample dataset
    assert all(p.is_mock for p in posts)


def test_mock_fetcher_keyword_filter_matches_text_case_insensitively():
    posts = MockFetcher().fetch(FetchQuery(community="ignored", keyword="SCHEDULER", limit=100))
    assert len(posts) >= 1
    assert all("scheduler" in (p.text + (p.title or "")).lower() for p in posts)


def test_mock_fetcher_keyword_filter_matches_title_too():
    posts = MockFetcher().fetch(FetchQuery(community="ignored", keyword="onboarding", limit=100))
    assert any(p.title and "onboarding" in p.title.lower() for p in posts)


def test_mock_fetcher_keyword_with_no_matches_returns_empty():
    posts = MockFetcher().fetch(FetchQuery(community="ignored", keyword="quantum blockchain nft", limit=100))
    assert posts == []


def test_mock_fetcher_respects_limit():
    posts = MockFetcher().fetch(FetchQuery(community="ignored", limit=2))
    assert len(posts) == 2


def test_mock_fetcher_ignores_community():
    a = MockFetcher().fetch(FetchQuery(community="startups", limit=100))
    b = MockFetcher().fetch(FetchQuery(community="totally_different", limit=100))
    assert [p.id for p in a] == [p.id for p in b]


# --- get_fetcher factory -----------------------------------------------------------


def test_factory_returns_mock_fetcher_when_reddit_not_configured():
    fetcher = get_fetcher(_config(reddit_configured=False))
    assert isinstance(fetcher, MockFetcher)


def test_factory_returns_reddit_fetcher_when_reddit_configured():
    fetcher = get_fetcher(_config(reddit_configured=True))
    assert isinstance(fetcher, RedditFetcher)


def test_factory_force_mock_overrides_configured_reddit():
    fetcher = get_fetcher(_config(reddit_configured=True), force_mock=True)
    assert isinstance(fetcher, MockFetcher)
