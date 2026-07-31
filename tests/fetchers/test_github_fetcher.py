"""Tests for src/fetchers/github_fetcher.py. All HTTP calls are mocked
(unittest.mock.patch on the module's own `requests.get` reference) —
never hits the real GitHub API, same offline-test discipline as every
other fetcher/provider test in this project.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from unittest.mock import patch

import pytest

from src.config import Config
from src.fetchers.base import FetcherError
from src.fetchers.exceptions import (
    FetcherAuthError,
    FetcherNotFoundError,
    FetcherRateLimitError,
)
from src.fetchers.github_fetcher import GitHubFetcher
from src.models import FetchQuery


def _config(token: Optional[str] = None) -> Config:
    return Config(
        gemini_api_key=None,
        gemini_model="gemini-flash-latest",
        reddit_client_id=None,
        reddit_client_secret=None,
        reddit_user_agent="test-agent",
        github_token=token,
    )


def _issue(
    number: int = 1,
    title: str = "Something is broken",
    body: str = "It broke.",
    login: str = "octocat",
    html_url: str = "https://github.com/owner/repo/issues/1",
    created_at: str = "2026-01-01T00:00:00Z",
    plus_one: int = 0,
    heart: int = 0,
    comments: int = 0,
) -> Dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "body": body,
        "user": {"login": login},
        "html_url": html_url,
        "created_at": created_at,
        "reactions": {"+1": plus_one, "heart": heart},
        "comments": comments,
    }


class _FakeResponse:
    def __init__(self, status_code: int, data: Any) -> None:
        self.status_code = status_code
        self._data = data

    def json(self) -> Any:
        return self._data


# --- Basic fetch behavior ----------------------------------------------------------


def test_fetch_returns_discussions():
    issues = [_issue(number=1), _issue(number=2), _issue(number=3)]
    responses = iter(
        [_FakeResponse(200, issues)]
        + [_FakeResponse(200, []) for _ in issues]  # comments for each issue
    )

    with patch("src.fetchers.github_fetcher.requests.get", side_effect=lambda *a, **k: next(responses)):
        posts = GitHubFetcher(_config()).fetch(FetchQuery(community="owner/repo", limit=3))

    assert len(posts) == 3
    assert all(p.source == "github" for p in posts)


def test_fetch_with_comments():
    issues = [_issue(number=1, body="Original body")]
    comments = [{"body": "First comment text"}, {"body": "Second comment text"}]
    responses = iter([_FakeResponse(200, issues), _FakeResponse(200, comments)])

    with patch("src.fetchers.github_fetcher.requests.get", side_effect=lambda *a, **k: next(responses)):
        posts = GitHubFetcher(_config()).fetch(FetchQuery(community="owner/repo", limit=1))

    assert "First comment text" in posts[0].text
    assert "Second comment text" in posts[0].text


def test_fetch_empty_repository():
    responses = iter([_FakeResponse(200, [])])

    with patch("src.fetchers.github_fetcher.requests.get", side_effect=lambda *a, **k: next(responses)):
        posts = GitHubFetcher(_config()).fetch(FetchQuery(community="owner/repo", limit=10))

    assert posts == []


def test_fetch_keyword_filter():
    issues = [
        _issue(number=1, title="Unrelated issue"),
        _issue(number=2, title="Reconciliation bug in payouts"),
        _issue(number=3, title="Another unrelated issue"),
    ]
    responses = iter([_FakeResponse(200, issues)] + [_FakeResponse(200, []) for _ in issues])

    with patch("src.fetchers.github_fetcher.requests.get", side_effect=lambda *a, **k: next(responses)):
        posts = GitHubFetcher(_config()).fetch(FetchQuery(community="owner/repo", keyword="reconciliation", limit=3))

    assert len(posts) == 1
    assert posts[0].title == "Reconciliation bug in payouts"


# --- Error handling ------------------------------------------------------------------


def test_fetch_repository_not_found():
    with patch("src.fetchers.github_fetcher.requests.get", return_value=_FakeResponse(404, {})):
        with pytest.raises(FetcherNotFoundError):
            GitHubFetcher(_config()).fetch(FetchQuery(community="owner/repo", limit=1))


def test_fetch_rate_limit_exceeded():
    with patch("src.fetchers.github_fetcher.requests.get", return_value=_FakeResponse(403, {})):
        with pytest.raises(FetcherRateLimitError):
            GitHubFetcher(_config()).fetch(FetchQuery(community="owner/repo", limit=1))


def test_fetch_invalid_token():
    with patch("src.fetchers.github_fetcher.requests.get", return_value=_FakeResponse(401, {})):
        with pytest.raises(FetcherAuthError):
            GitHubFetcher(_config(token="bad-token")).fetch(FetchQuery(community="owner/repo", limit=1))


def test_fetch_other_error_status_raises_generic_fetcher_error():
    with patch("src.fetchers.github_fetcher.requests.get", return_value=_FakeResponse(500, {})):
        with pytest.raises(FetcherError):
            GitHubFetcher(_config()).fetch(FetchQuery(community="owner/repo", limit=1))


# --- Auth header behavior --------------------------------------------------------------


def test_fetch_with_token_sets_auth_header():
    captured_headers = {}

    def _fake_get(url, headers=None, params=None, timeout=None):
        captured_headers.update(headers or {})
        return _FakeResponse(200, [])

    with patch("src.fetchers.github_fetcher.requests.get", side_effect=_fake_get):
        GitHubFetcher(_config(token="real-token-123")).fetch(FetchQuery(community="owner/repo", limit=1))

    assert captured_headers.get("Authorization") == "Bearer real-token-123"


def test_fetch_without_token_no_auth_header():
    captured_headers = {}

    def _fake_get(url, headers=None, params=None, timeout=None):
        captured_headers.update(headers or {})
        return _FakeResponse(200, [])

    with patch("src.fetchers.github_fetcher.requests.get", side_effect=_fake_get):
        posts = GitHubFetcher(_config(token=None)).fetch(FetchQuery(community="owner/repo", limit=1))

    assert "Authorization" not in captured_headers
    assert posts == []


# --- Field mapping ---------------------------------------------------------------------


def test_discussion_field_mapping():
    issue = _issue(
        number=42,
        title="Exact title",
        body="Exact body",
        login="some_user",
        html_url="https://github.com/owner/repo/issues/42",
        created_at="2026-03-15T10:30:00Z",
        plus_one=3,
        heart=2,
    )
    responses = iter([_FakeResponse(200, [issue]), _FakeResponse(200, [])])

    with patch("src.fetchers.github_fetcher.requests.get", side_effect=lambda *a, **k: next(responses)):
        posts = GitHubFetcher(_config()).fetch(FetchQuery(community="owner/repo", limit=1))

    post = posts[0]
    assert post.title == "Exact title"
    assert "Exact body" in post.text
    assert post.url == "https://github.com/owner/repo/issues/42"
    assert post.author == "some_user"
    assert post.score == 5  # reactions["+1"] (3) + reactions["heart"] (2)
    assert post.source == "github"
    assert post.is_mock is False
    assert post.created_at.year == 2026 and post.created_at.month == 3 and post.created_at.day == 15
