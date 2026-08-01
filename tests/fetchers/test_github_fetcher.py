"""Tests for src/fetchers/github_fetcher.py. All HTTP calls are mocked
(unittest.mock.patch on the module's own `requests.get` reference) —
never hits the real GitHub API, same offline-test discipline as every
other fetcher/provider test in this project.

GitHubFetcher searches GitHub's Search Issues API (/search/issues)
directly with query.keyword - no repository is ever specified by the
caller, and no repo-discovery step happens first (see the module
docstring for why the old repo-discovery design was replaced). Every
test below mocks that single search endpoint (plus the per-issue
comments endpoint), via _MockGitHubAPI, which routes a fake
requests.get by URL shape and records every call so tests can assert
on what was actually requested.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest

from src.config import Config
from src.fetchers.base import FetcherError
from src.fetchers.exceptions import FetcherRateLimitError
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
    title: str = "invoice automation is broken",
    body: str = "invoice automation takes forever to reconcile.",
    login: str = "octocat",
    repo: str = "owner/repo",
    created_at: str = "2026-01-01T00:00:00Z",
    plus_one: int = 0,
    heart: int = 0,
) -> Dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "body": body,
        "user": {"login": login},
        "html_url": f"https://github.com/{repo}/issues/{number}",
        "repository_url": f"https://api.github.com/repos/{repo}",
        "created_at": created_at,
        "reactions": {"+1": plus_one, "heart": heart},
    }


class _FakeResponse:
    def __init__(self, status_code: int, data: Any) -> None:
        self.status_code = status_code
        self._data = data

    def json(self) -> Any:
        return self._data


class _MockGitHubAPI:
    """Fake requests.get, routed by URL shape.

    search_pages answers successive GET .../search/issues calls (one
    entry per `page` param, 1-indexed via list position) - defaults to
    a single empty page if unset. Comments are always answered with an
    empty list unless comments_responses[(repo, number)] is set. Every
    call is recorded in .calls for assertions.
    """

    def __init__(self) -> None:
        self.search_pages: List[_FakeResponse] = []
        self.comments_responses: Dict[tuple, _FakeResponse] = {}
        self.calls: List[Dict[str, Any]] = []

    def __call__(self, url: str, headers=None, params=None, timeout=None) -> _FakeResponse:
        self.calls.append({"url": url, "params": params, "headers": headers})
        if url.endswith("/search/issues"):
            page = (params or {}).get("page", 1)
            index = page - 1
            if 0 <= index < len(self.search_pages):
                return self.search_pages[index]
            return _FakeResponse(200, {"items": []})
        if "/comments" in url:
            repo_and_number = _repo_and_number_from_comments_url(url)
            return self.comments_responses.get(repo_and_number, _FakeResponse(200, []))
        raise AssertionError(f"unexpected URL in test: {url}")


def _repo_and_number_from_comments_url(url: str) -> tuple:
    # ".../repos/{owner}/{repo}/issues/{number}/comments"
    after = url.split("/repos/", 1)[1]
    parts = after.split("/")
    repo = "/".join(parts[:2])
    number = int(parts[3])
    return (repo, number)


def _patch_requests(api: _MockGitHubAPI):
    return patch("src.fetchers.github_fetcher.requests.get", side_effect=api)


# --- fetch(): keyword-only search, no repository specified ---------------------------


def test_fetch_requires_keyword():
    with pytest.raises(FetcherError):
        GitHubFetcher(_config()).fetch(FetchQuery(community="ignored", keyword=None, limit=5))


def test_fetch_searches_issues_directly_with_no_repository_specified():
    """The core behavior this task exists to add: a bare keyword (no
    repo, no owner/repo string anywhere in the call) finds matching
    issues across all of public GitHub via a single Search Issues call.
    """
    api = _MockGitHubAPI()
    api.search_pages = [_FakeResponse(200, {"items": [_issue(number=1, repo="invoiceninja/invoiceninja")]})]

    with _patch_requests(api):
        posts = GitHubFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoice automation", limit=5))

    assert len(posts) == 1
    assert posts[0].source == "github"
    search_calls = [call for call in api.calls if call["url"].endswith("/search/issues")]
    assert len(search_calls) == 1
    assert search_calls[0]["params"]["q"] == "invoice automation type:issue is:open"
    # No repo-search or per-repo issues-list endpoint is ever hit.
    assert not any("/search/repositories" in call["url"] for call in api.calls)


def test_fetch_matches_issues_whose_repo_name_does_not_contain_the_keyword():
    """Regression guard for the exact problem the old repo-discovery
    design had: a repo named "billing-service" would never have
    surfaced under a repo-name/description/topic search for "invoice
    automation", but its issues can still genuinely be about it. Search
    Issues matches issue text directly, so this now works.
    """
    api = _MockGitHubAPI()
    api.search_pages = [
        _FakeResponse(
            200,
            {
                "items": [
                    _issue(
                        number=7,
                        title="Automate invoice generation on payment",
                        body="Need to auto-generate an invoice automation workflow when a payment succeeds.",
                        repo="someorg/billing-service",
                    )
                ]
            },
        )
    ]

    with _patch_requests(api):
        posts = GitHubFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoice automation", limit=5))

    assert len(posts) == 1
    assert posts[0].title == "Automate invoice generation on payment"


def test_fetch_paginates_when_limit_exceeds_one_page():
    api = _MockGitHubAPI()
    api.search_pages = [
        _FakeResponse(200, {"items": [_issue(number=i) for i in range(1, 101)]}),  # page 1: full 100
        _FakeResponse(200, {"items": [_issue(number=101)]}),  # page 2: 1 more
    ]

    with _patch_requests(api):
        posts = GitHubFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=101))

    assert len(posts) == 101
    search_calls = [call for call in api.calls if call["url"].endswith("/search/issues")]
    assert [call["params"]["page"] for call in search_calls] == [1, 2]
    assert search_calls[0]["params"]["per_page"] == 100
    assert search_calls[1]["params"]["per_page"] == 1


def test_fetch_stops_paging_once_a_page_returns_fewer_than_requested():
    """A short page means the search is exhausted - no further page
    request should be made even if `limit` wasn't fully reached.
    """
    api = _MockGitHubAPI()
    api.search_pages = [_FakeResponse(200, {"items": [_issue(number=1), _issue(number=2)]})]

    with _patch_requests(api):
        posts = GitHubFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=50))

    assert len(posts) == 2
    search_calls = [call for call in api.calls if call["url"].endswith("/search/issues")]
    assert len(search_calls) == 1


def test_fetch_no_results_raises():
    api = _MockGitHubAPI()
    api.search_pages = [_FakeResponse(200, {"items": []})]

    with _patch_requests(api):
        with pytest.raises(FetcherError):
            GitHubFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))


def test_fetch_search_rate_limit_exceeded():
    api = _MockGitHubAPI()
    api.search_pages = [_FakeResponse(403, {})]

    with _patch_requests(api):
        with pytest.raises(FetcherRateLimitError):
            GitHubFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))


def test_fetch_invalid_keyword():
    api = _MockGitHubAPI()
    api.search_pages = [_FakeResponse(422, {})]

    with _patch_requests(api):
        with pytest.raises(FetcherError):
            GitHubFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))


# --- Auth header behavior --------------------------------------------------------------


def test_fetch_with_token_sets_auth_header_on_search_and_comments_calls():
    api = _MockGitHubAPI()
    api.search_pages = [_FakeResponse(200, {"items": [_issue(number=1)]})]
    api.comments_responses[("owner/repo", 1)] = _FakeResponse(200, [{"body": "a comment"}])

    with _patch_requests(api):
        GitHubFetcher(_config(token="real-token-123")).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=5))

    assert all(call["headers"].get("Authorization") == "Bearer real-token-123" for call in api.calls)


def test_fetch_without_token_no_auth_header():
    api = _MockGitHubAPI()
    api.search_pages = [_FakeResponse(200, {"items": [_issue(number=1)]})]

    with _patch_requests(api):
        posts = GitHubFetcher(_config(token=None)).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=5))

    assert all("Authorization" not in call["headers"] for call in api.calls)
    assert len(posts) == 1


# --- Field mapping ---------------------------------------------------------------------


def test_discussion_field_mapping():
    issue = _issue(
        number=42,
        title="invoicing takes too long",
        body="invoicing body text",
        login="some_user",
        repo="owner/repo",
        created_at="2026-03-15T10:30:00Z",
        plus_one=3,
        heart=2,
    )
    api = _MockGitHubAPI()
    api.search_pages = [_FakeResponse(200, {"items": [issue]})]

    with _patch_requests(api):
        posts = GitHubFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=1))

    post = posts[0]
    assert post.id == "owner/repo#42"
    assert post.title == "invoicing takes too long"
    assert "invoicing body text" in post.text
    assert post.url == "https://github.com/owner/repo/issues/42"
    assert post.author == "some_user"
    assert post.score == 5  # reactions["+1"] (3) + reactions["heart"] (2)
    assert post.source == "github"
    assert post.is_mock is False
    assert post.created_at.year == 2026 and post.created_at.month == 3 and post.created_at.day == 15


def test_comments_are_folded_into_post_text():
    api = _MockGitHubAPI()
    api.search_pages = [_FakeResponse(200, {"items": [_issue(number=1, repo="owner/repo")]})]
    api.comments_responses[("owner/repo", 1)] = _FakeResponse(200, [{"body": "first comment"}, {"body": "second comment"}])

    with _patch_requests(api):
        posts = GitHubFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=1))

    assert "first comment" in posts[0].text
    assert "second comment" in posts[0].text
