"""Tests for src/fetchers/hn_fetcher.py. All HTTP calls are mocked
(unittest.mock.patch on the module's own `requests.get` reference) -
never hits the real Algolia API, same offline-test discipline as
tests/fetchers/test_github_fetcher.py.

Every hit fixture's title contains the search keyword ("invoicing")
unless a test is specifically about the quality filter dropping it
before the keyword filter would even matter - HNFetcher.fetch() applies
BOTH filters (see its own STEP 2/STEP 4 in the module docstring), so a
fixture that's supposed to survive must satisfy both.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest
import requests

from src.config import Config
from src.fetchers import get_fetcher
from src.fetchers.base import FetcherError
from src.fetchers.hn_fetcher import HNFetcher
from src.models import FetchQuery


def _config() -> Config:
    return Config(
        gemini_api_key=None,
        gemini_model="gemini-flash-latest",
        reddit_client_id=None,
        reddit_client_secret=None,
        reddit_user_agent="test-agent",
    )


def _hit(
    object_id: str = "111",
    title: str = "invoicing tool for freelancers",
    story_text: Optional[str] = "Looking for feedback on my invoicing side project.",
    url: Optional[str] = "https://example.com/invoicing-tool",
    author: str = "some_user",
    points: int = 50,
    created_at: str = "2026-01-01T00:00:00.000Z",
    num_comments: int = 10,
) -> Dict[str, Any]:
    return {
        "objectID": object_id,
        "title": title,
        "story_text": story_text,
        "url": url,
        "author": author,
        "points": points,
        "created_at": created_at,
        "num_comments": num_comments,
    }


class _FakeResponse:
    def __init__(self, status_code: int, data: Any) -> None:
        self.status_code = status_code
        self._data = data

    def json(self) -> Any:
        return self._data


def _patch_requests(response: Any = None, side_effect: Any = None):
    kwargs = {"side_effect": side_effect} if side_effect is not None else {"return_value": response}
    return patch("src.fetchers.hn_fetcher.requests.get", **kwargs)


# --- fetch(): basic search + field mapping ----------------------------------------


def test_fetch_returns_discussions():
    hits = [_hit(object_id=str(i), title=f"invoicing discussion {i}") for i in range(3)]
    with _patch_requests(_FakeResponse(200, {"hits": hits})):
        posts = HNFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))

    assert len(posts) == 3
    assert all(p.source == "hackernews" for p in posts)


def test_discussion_fields_correct():
    hit = _hit(
        object_id="999",
        title="invoicing pain points",
        story_text="Real body text about invoicing.",
        url="https://example.com/story",
        author="jdoe",
        points=42,
        created_at="2026-03-15T10:30:00.000Z",
        num_comments=7,
    )
    with _patch_requests(_FakeResponse(200, {"hits": [hit]})):
        posts = HNFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=5))

    post = posts[0]
    assert post.id == "999"
    assert post.title == "invoicing pain points"
    assert post.text == "Real body text about invoicing."
    assert post.url == "https://news.ycombinator.com/item?id=999"
    assert post.author == "jdoe"
    assert post.score == 42
    assert post.source == "hackernews"
    assert post.item_type == "post"
    assert post.is_mock is False
    assert post.created_at.year == 2026 and post.created_at.month == 3 and post.created_at.day == 15
    assert post.raw["num_comments"] == 7


# --- Quality filter -----------------------------------------------------------------


def test_fetch_filters_hiring_posts():
    hits = [
        _hit(object_id="1", title="Ask HN: Who is hiring? (invoicing edition)"),
        _hit(object_id="2", title="invoicing tool launched"),
    ]
    with _patch_requests(_FakeResponse(200, {"hits": hits})):
        posts = HNFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))

    assert all("who is hiring" not in (p.title or "").lower() for p in posts)
    assert any(p.id == "2" for p in posts)
    assert not any(p.id == "1" for p in posts)


def test_fetch_filters_low_points():
    hits = [
        _hit(object_id="1", title="invoicing tool with low points", points=2),
        _hit(object_id="2", title="invoicing tool with real traction", points=50),
    ]
    with _patch_requests(_FakeResponse(200, {"hits": hits})):
        posts = HNFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))

    assert not any(p.id == "1" for p in posts)
    assert any(p.id == "2" for p in posts)


# --- Empty results, null body, truncation --------------------------------------------


def test_fetch_empty_results():
    with _patch_requests(_FakeResponse(200, {"hits": []})):
        posts = HNFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))

    assert posts == []


def test_fetch_null_body_handled():
    hit = _hit(object_id="1", title="invoicing story with no body", story_text=None)
    with _patch_requests(_FakeResponse(200, {"hits": [hit]})):
        posts = HNFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))  # must not raise

    assert len(posts) == 1
    assert posts[0].text == "HN Discussion: invoicing story with no body"


def test_fetch_body_truncated():
    long_body = "x" * 3000
    hit = _hit(object_id="1", title="invoicing long story", story_text=long_body)
    with _patch_requests(_FakeResponse(200, {"hits": [hit]})):
        posts = HNFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))

    assert len(posts[0].text) <= 1600
    assert "[Content truncated for analysis]" in posts[0].text


# --- Error handling -------------------------------------------------------------------


def test_fetch_timeout_raises_error():
    with _patch_requests(side_effect=requests.Timeout()):
        with pytest.raises(FetcherError):
            HNFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))


def test_fetch_non_200_raises_error():
    with _patch_requests(_FakeResponse(500, {})):
        with pytest.raises(FetcherError):
            HNFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))


def test_fetch_requires_keyword():
    with pytest.raises(FetcherError):
        HNFetcher(_config()).fetch(FetchQuery(community="ignored", keyword=None, limit=10))


# --- Factory registration --------------------------------------------------------------


def test_factory_returns_hn_fetcher():
    fetcher = get_fetcher(_config(), source="hackernews")
    assert isinstance(fetcher, HNFetcher)


def test_factory_hn_alias_works():
    fetcher = get_fetcher(_config(), source="hn")
    assert isinstance(fetcher, HNFetcher)
