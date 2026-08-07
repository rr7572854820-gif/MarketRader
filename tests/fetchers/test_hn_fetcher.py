"""Tests for src/fetchers/hn_fetcher.py. All HTTP calls are mocked
(unittest.mock.patch on the module's own `requests.get` reference) -
never hits the real Algolia API, same offline-test discipline as
tests/fetchers/test_github_fetcher.py.

Most hit fixtures' titles contain "invoicing" out of habit from before
the post-fetch keyword-presence filter was removed - no longer load-
bearing for most tests (only the quality filter - points, hiring/poll -
still applies), but test_fetch_keeps_posts_not_containing_the_keyword
exists specifically to prove that isn't required anymore.
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


# --- original_keyword preference (over AI-expanded keyword/keywords) ----------------


def test_fetch_searches_original_keyword_when_set():
    """When QueryExpander has run (source="github"/"all" -
    src/pipeline/pipeline.py), query.keyword carries an AI-expanded,
    technical-sounding term meant for GitHub's Search Issues API - HN
    must search query.original_keyword (the user's real, short, broad
    input) instead, not the expanded one.
    """
    captured: Dict[str, Any] = {}

    def _capture(url, params=None, timeout=None):
        captured["query_param"] = params.get("query") if params else None
        return _FakeResponse(200, {"hits": []})

    with _patch_requests(side_effect=_capture):
        HNFetcher(_config()).fetch(
            FetchQuery(
                community="ignored",
                keyword="api gateway architecture",
                keywords=["api gateway architecture", "restful api design"],
                original_keyword="api",
                limit=10,
            )
        )

    assert captured["query_param"] == "api"


def test_fetch_falls_back_to_keyword_when_no_original_keyword():
    """No QueryExpander run (e.g. source="hackernews" alone, or any
    caller that never sets original_keyword) - query.keyword is already
    the user's real input, so that's what gets searched, unchanged.
    """
    captured: Dict[str, Any] = {}

    def _capture(url, params=None, timeout=None):
        captured["query_param"] = params.get("query") if params else None
        return _FakeResponse(200, {"hits": []})

    with _patch_requests(side_effect=_capture):
        HNFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))

    assert captured["query_param"] == "invoicing"


# --- No post-fetch keyword-presence filter (removed) ---------------------------------


def test_fetch_keeps_posts_not_containing_the_keyword():
    """The post-fetch keyword-presence re-check was removed (live-
    verified to drop too many real, on-topic results) - a quality-
    passing hit whose title/body doesn't literally repeat the search
    term must still come through, relying on Algolia's own search
    relevance instead.
    """
    hit = _hit(object_id="1", title="A tool for freelance billing and payment tracking")
    with _patch_requests(_FakeResponse(200, {"hits": [hit]})):
        posts = HNFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))

    assert len(posts) == 1
    assert posts[0].id == "1"


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
    # 0 is below _MIN_POINTS (1) - genuinely zero-signal, still filtered.
    hits = [
        _hit(object_id="1", title="invoicing tool with zero points", points=0),
        _hit(object_id="2", title="invoicing tool with real traction", points=50),
    ]
    with _patch_requests(_FakeResponse(200, {"hits": hits})):
        posts = HNFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))

    assert not any(p.id == "1" for p in posts)
    assert any(p.id == "2" for p in posts)


def test_fetch_keeps_low_but_nonzero_points():
    """_MIN_POINTS was lowered from 5 to 1 (live-verified: >5 dropped
    too many real, on-topic results) - a story with 1-4 points must now
    survive the filter, where it previously wouldn't have.
    """
    hit = _hit(object_id="1", title="invoicing tool with modest traction", points=2)
    with _patch_requests(_FakeResponse(200, {"hits": [hit]})):
        posts = HNFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))

    assert any(p.id == "1" for p in posts)


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
