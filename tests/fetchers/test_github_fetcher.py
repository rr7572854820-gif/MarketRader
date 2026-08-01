"""Tests for src/fetchers/github_fetcher.py. All HTTP calls are mocked
(unittest.mock.patch on the module's own `requests.get` reference) —
never hits the real GitHub API, same offline-test discipline as every
other fetcher/provider test in this project.

GitHubFetcher no longer takes an explicit repo - every fetch() call now
discovers candidate repos from query.keyword via GitHub's Search API
first, then fetches issues from each. Every test below therefore mocks
the search endpoint too, via _MockGitHubAPI, which routes a fake
requests.get by URL shape (search vs. issues vs. comments) and records
every call so tests can assert on what was actually requested (e.g.
per-repo page-size distribution), not just on the final result.

Because fetch()'s final step re-applies the same keyword as a filter on
the combined results (see github_fetcher.py's fetch() docstring), every
mocked issue expected to survive uses "invoicing" as the test keyword
throughout, in either its title or body.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
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
    title: str = "invoicing is broken",
    body: str = "invoicing takes forever to reconcile.",
    login: str = "octocat",
    html_url: str = "https://github.com/owner/repo/issues/1",
    created_at: str = "2026-01-01T00:00:00Z",
    plus_one: int = 0,
    heart: int = 0,
) -> Dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "body": body,
        "user": {"login": login},
        "html_url": html_url,
        "created_at": created_at,
        "reactions": {"+1": plus_one, "heart": heart},
    }


def _repo_item(full_name: str, *, archived: bool = False, fork: bool = False, open_issues_count: int = 5) -> Dict[str, Any]:
    return {"full_name": full_name, "archived": archived, "fork": fork, "open_issues_count": open_issues_count}


class _FakeResponse:
    def __init__(self, status_code: int, data: Any) -> None:
        self.status_code = status_code
        self._data = data

    def json(self) -> Any:
        return self._data


def _repo_from_issues_url(url: str) -> str:
    after = url.split("/repos/", 1)[1]
    return after.rsplit("/issues", 1)[0]


class _MockGitHubAPI:
    """Fake requests.get, routed by URL shape. search_response answers
    GET .../search/repositories; issues_responses[repo] answers GET
    .../repos/{repo}/issues (defaulting to an empty list); comments are
    always answered with an empty list (no test here needs comment
    bodies). Every call is recorded in .calls for assertions.
    """

    def __init__(self) -> None:
        self.search_response: Optional[_FakeResponse] = None
        self.issues_responses: Dict[str, _FakeResponse] = {}
        self.calls: List[Dict[str, Any]] = []

    def __call__(self, url: str, headers=None, params=None, timeout=None) -> _FakeResponse:
        self.calls.append({"url": url, "params": params, "headers": headers})
        if url.endswith("/search/repositories"):
            assert self.search_response is not None, "test forgot to set search_response"
            return self.search_response
        if "/comments" in url:
            return _FakeResponse(200, [])
        repo = _repo_from_issues_url(url)
        return self.issues_responses.get(repo, _FakeResponse(200, []))


def _patch_requests(api: _MockGitHubAPI):
    return patch("src.fetchers.github_fetcher.requests.get", side_effect=api)


# --- discover_repos -----------------------------------------------------------------


def test_discover_repos_returns_top5():
    repos = [f"owner/repo{i}" for i in range(5)]
    api = _MockGitHubAPI()
    api.search_response = _FakeResponse(200, {"items": [_repo_item(r) for r in repos]})

    with _patch_requests(api):
        result = GitHubFetcher(_config()).discover_repos("invoicing", max_repos=5)

    assert result == repos


def test_discover_repos_filters_archived():
    api = _MockGitHubAPI()
    api.search_response = _FakeResponse(
        200,
        {"items": [_repo_item("owner/good1"), _repo_item("owner/archived", archived=True), _repo_item("owner/good2")]},
    )

    with _patch_requests(api):
        result = GitHubFetcher(_config()).discover_repos("invoicing")

    assert result == ["owner/good1", "owner/good2"]


def test_discover_repos_filters_forks():
    api = _MockGitHubAPI()
    api.search_response = _FakeResponse(
        200,
        {"items": [_repo_item("owner/good1"), _repo_item("owner/afork", fork=True), _repo_item("owner/good2")]},
    )

    with _patch_requests(api):
        result = GitHubFetcher(_config()).discover_repos("invoicing")

    assert result == ["owner/good1", "owner/good2"]


def test_discover_repos_filters_no_issues():
    api = _MockGitHubAPI()
    api.search_response = _FakeResponse(
        200,
        {
            "items": [
                _repo_item("owner/good1"),
                _repo_item("owner/dead", open_issues_count=0),
                _repo_item("owner/good2"),
            ]
        },
    )

    with _patch_requests(api):
        result = GitHubFetcher(_config()).discover_repos("invoicing")

    assert result == ["owner/good1", "owner/good2"]


def test_discover_repos_no_results():
    api = _MockGitHubAPI()
    api.search_response = _FakeResponse(200, {"items": [_repo_item("owner/archived", archived=True)]})

    with _patch_requests(api):
        with pytest.raises(FetcherError):
            GitHubFetcher(_config()).discover_repos("invoicing")


def test_discover_repos_search_rate_limit_exceeded():
    api = _MockGitHubAPI()
    api.search_response = _FakeResponse(403, {})

    with _patch_requests(api):
        with pytest.raises(FetcherRateLimitError):
            GitHubFetcher(_config()).discover_repos("invoicing")


def test_discover_repos_invalid_keyword():
    api = _MockGitHubAPI()
    api.search_response = _FakeResponse(422, {})

    with _patch_requests(api):
        with pytest.raises(FetcherError):
            GitHubFetcher(_config()).discover_repos("invoicing")


# --- fetch(): discovery-driven flow --------------------------------------------------


def test_fetch_requires_keyword():
    with pytest.raises(FetcherError):
        GitHubFetcher(_config()).fetch(FetchQuery(community="ignored", keyword=None, limit=5))


def test_fetch_uses_discovery():
    api = _MockGitHubAPI()
    api.search_response = _FakeResponse(200, {"items": [_repo_item("owner/repo1")]})
    api.issues_responses["owner/repo1"] = _FakeResponse(200, [_issue(number=1)])

    with _patch_requests(api):
        posts = GitHubFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=5))

    assert len(posts) == 1
    assert posts[0].source == "github"
    assert any(call["url"].endswith("/search/repositories") for call in api.calls)


def test_fetch_distributes_limit():
    repos = [f"owner/repo{i}" for i in range(5)]
    api = _MockGitHubAPI()
    api.search_response = _FakeResponse(200, {"items": [_repo_item(r) for r in repos]})
    for r in repos:
        api.issues_responses[r] = _FakeResponse(200, [])

    with _patch_requests(api):
        GitHubFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=25))

    issues_calls = [
        call for call in api.calls if not call["url"].endswith("/search/repositories") and "/comments" not in call["url"]
    ]
    assert len(issues_calls) == 5
    assert all(call["params"]["per_page"] == 5 for call in issues_calls)


def test_fetch_skips_failed_repo():
    api = _MockGitHubAPI()
    api.search_response = _FakeResponse(200, {"items": [_repo_item("owner/bad"), _repo_item("owner/good")]})
    api.issues_responses["owner/bad"] = _FakeResponse(404, {})
    api.issues_responses["owner/good"] = _FakeResponse(200, [_issue(number=1)])

    with _patch_requests(api):
        posts = GitHubFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))

    assert len(posts) == 1


def test_fetch_all_repos_fail():
    api = _MockGitHubAPI()
    api.search_response = _FakeResponse(200, {"items": [_repo_item("owner/bad1"), _repo_item("owner/bad2")]})
    api.issues_responses["owner/bad1"] = _FakeResponse(500, {})
    api.issues_responses["owner/bad2"] = _FakeResponse(500, {})

    with _patch_requests(api):
        with pytest.raises(FetcherError):
            GitHubFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))


def test_fetch_does_not_re_filter_issues_by_literal_keyword():
    """Real-world regression test: an early version re-applied `keyword`
    as a manual substring filter on each issue's title/body after
    fetching, on top of discover_repos() already using it as the
    GitHub Search API query. Live-tested against real repos found for
    "invoicing" (invoiceninja/invoiceninja, akaunting/akaunting, etc.)
    and reverted after confirming it silently zeroed out every result -
    real issues in those repos (e.g. "Fix PDF export") don't repeat the
    word "invoicing," so a topically-correct fetch returned 0
    discussions. Repo-level relevance from discover_repos is the real
    filter (the same precedent RedditFetcher already set by delegating
    to subreddit.search() instead of re-filtering); an issue's own text
    is never required to repeat the search term.
    """
    api = _MockGitHubAPI()
    api.search_response = _FakeResponse(200, {"items": [_repo_item("owner/repo1")]})
    api.issues_responses["owner/repo1"] = _FakeResponse(
        200,
        [
            _issue(number=1, title="invoicing is broken", body="nothing relevant here"),
            _issue(number=2, title="Fix PDF export", body="totally unrelated body text"),
        ],
    )

    with _patch_requests(api):
        posts = GitHubFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))

    assert len(posts) == 2
    assert {post.title for post in posts} == {"invoicing is broken", "Fix PDF export"}


# --- Auth header behavior --------------------------------------------------------------


def test_fetch_with_token_sets_auth_header_on_search_and_issues_calls():
    api = _MockGitHubAPI()
    api.search_response = _FakeResponse(200, {"items": [_repo_item("owner/repo1")]})
    api.issues_responses["owner/repo1"] = _FakeResponse(200, [_issue(number=1)])

    with _patch_requests(api):
        GitHubFetcher(_config(token="real-token-123")).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=5))

    assert all(call["headers"].get("Authorization") == "Bearer real-token-123" for call in api.calls)


def test_fetch_without_token_no_auth_header():
    api = _MockGitHubAPI()
    api.search_response = _FakeResponse(200, {"items": [_repo_item("owner/repo1")]})
    api.issues_responses["owner/repo1"] = _FakeResponse(200, [_issue(number=1)])

    with _patch_requests(api):
        posts = GitHubFetcher(_config(token=None)).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=5))

    assert all("Authorization" not in call["headers"] for call in api.calls)
    assert len(posts) == 1


def test_fetch_invalid_token_on_issues_call_is_skipped_not_raised():
    """401 on a per-repo issue fetch is still just a fetch failure for
    that one repo - see error-handling spec ("individual repo fetch
    fails -> skip, continue"). Only a fully-invalid search-level token
    would surface as FetcherAuthError from discover_repos itself
    (GitHub's search endpoint doesn't 401 on a bad-but-present token in
    practice; this documents the actual, current behavior instead of
    an untested assumption).
    """
    api = _MockGitHubAPI()
    api.search_response = _FakeResponse(200, {"items": [_repo_item("owner/bad"), _repo_item("owner/good")]})
    api.issues_responses["owner/bad"] = _FakeResponse(401, {})
    api.issues_responses["owner/good"] = _FakeResponse(200, [_issue(number=1)])

    with _patch_requests(api):
        posts = GitHubFetcher(_config(token="bad-token")).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))

    assert len(posts) == 1


# --- Field mapping ---------------------------------------------------------------------


def test_discussion_field_mapping():
    issue = _issue(
        number=42,
        title="invoicing takes too long",
        body="invoicing body text",
        login="some_user",
        html_url="https://github.com/owner/repo/issues/42",
        created_at="2026-03-15T10:30:00Z",
        plus_one=3,
        heart=2,
    )
    api = _MockGitHubAPI()
    api.search_response = _FakeResponse(200, {"items": [_repo_item("owner/repo")]})
    api.issues_responses["owner/repo"] = _FakeResponse(200, [issue])

    with _patch_requests(api):
        posts = GitHubFetcher(_config()).fetch(FetchQuery(community="ignored", keyword="invoicing", limit=1))

    post = posts[0]
    assert post.title == "invoicing takes too long"
    assert "invoicing body text" in post.text
    assert post.url == "https://github.com/owner/repo/issues/42"
    assert post.author == "some_user"
    assert post.score == 5  # reactions["+1"] (3) + reactions["heart"] (2)
    assert post.source == "github"
    assert post.is_mock is False
    assert post.created_at.year == 2026 and post.created_at.month == 3 and post.created_at.day == 15
