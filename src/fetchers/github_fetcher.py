"""Real GitHub Issues fetcher, read-only, via the GitHub REST API.

Only constructed by the factory (src/fetchers/__init__.py) when explicitly
selected via get_fetcher(config, source="github") - unlike Reddit, there's
no config flag that makes GitHub "configured" or not. GITHUB_TOKEN is
optional and only affects rate limits (60/hour public vs 5000/hour
authenticated).

Search strategy: GitHub's Search Issues API (/search/issues), which
matches a keyword directly against issue titles and bodies across all
of public GitHub. This replaced an earlier two-step design (Search
Repositories API to find candidate repos by name/description/topic,
then list each repo's open issues) - reverted after confirming by
inspection that repo-name matching is the wrong filter for this
fetcher's actual job. A keyword like "invoice automation" describes
the *problem*, not a product name: it won't appear in a repo's name,
description, or topics even when that repo's issues genuinely discuss
exactly that pain point (e.g. an issue titled "Automate invoice
generation on payment" in a repo just called "billing-service"). The
old design filtered on repo identity as a proxy for issue relevance;
Search Issues drops the proxy and matches the actual issue text
directly, so a keyword search no longer depends on a repo maintainer
having used the same words to name their project.

Nothing in here should be imported directly by pipeline code - see
src/fetchers/base.py.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from src.config import Config
from src.fetchers.base import Fetcher, FetcherError
from src.fetchers.exceptions import (
    FetcherAuthError,
    FetcherNotFoundError,
    FetcherRateLimitError,
)
from src.models import FetchedPost, FetchQuery

logger = logging.getLogger(__name__)

_API_BASE = "https://api.github.com"
_TIMEOUT_SECONDS = 10
_MAX_PER_PAGE = 100
# GitHub's Search API never returns more than 1000 results for a given
# query, regardless of pagination (documented API limit) - 10 pages of
# 100 is that ceiling, so paging past it would only ever 422 or repeat.
_MAX_SEARCH_PAGES = 10

_DEFAULT_RATE_LIMIT_MESSAGE = "GitHub rate limit exceeded. Add GITHUB_TOKEN to .env for higher limits."
_DEFAULT_INVALID_MESSAGE = "GitHub API rejected the request as malformed."


class GitHubFetcher(Fetcher):
    """Searches public GitHub issues directly for query.keyword via the
    Search Issues API, then fetches each match's comments.

    query.community is not used - GitHub has no analogous concept here
    (see FetchQuery's own docstring: fetchers are free to ignore fields
    that don't apply to their source, the same way MockFetcher ignores
    most of the query). A keyword is required, not optional, for this
    fetcher specifically - it is the entire search query.

    Each issue becomes exactly one FetchedPost (item_type="post"); its
    comments are appended into that same post's text rather than
    becoming their own FetchedPost items - unchanged from the previous
    design, see TODO.md.
    """

    def __init__(self, config: Config) -> None:
        self._token = config.github_token

    def fetch(self, query: FetchQuery) -> List[FetchedPost]:
        """Search GitHub issues for query.keyword and fetch each match's
        comments.

        Raises:
            FetcherError: If query.keyword is missing/blank, if the
                search query is rejected (422), or if zero issues match.
            FetcherRateLimitError: The search API's own rate limit was
                hit (403).
        """
        if not query.keyword:
            raise FetcherError("A keyword is required to search GitHub issues.")

        issues = self._search_issues(query.keyword, query.limit)
        if not issues:
            raise FetcherError(f"No open GitHub issues found matching '{query.keyword}'.")

        return [self._issue_to_post(issue) for issue in issues]

    def _search_issues(self, keyword: str, limit: int) -> List[Dict[str, Any]]:
        """Fetches up to `limit` open issues matching keyword, paging
        through the Search Issues API (100 per page max) as needed.

        Ranked by GitHub's own relevance ("best match") ordering rather
        than a sort=created/updated override - for a free-text keyword
        search across all of GitHub, textual relevance to the query is
        the right ranking, unlike the old per-repo design (there,
        relevance was already established by discover_repos, so sorting
        each repo's own issues by recency made sense; that reasoning no
        longer applies once a single search spans every public repo).
        """
        remaining = max(1, limit)
        results: List[Dict[str, Any]] = []
        page = 1
        while remaining > 0 and page <= _MAX_SEARCH_PAGES:
            per_page = min(remaining, _MAX_PER_PAGE)
            data = self._get_json(
                f"{_API_BASE}/search/issues",
                params={
                    "q": f"{keyword} type:issue is:open",
                    "per_page": per_page,
                    "page": page,
                },
                rate_limit_message="GitHub search rate limit exceeded.",
                invalid_message="Invalid search keyword.",
            )
            items = data.get("items", []) if isinstance(data, dict) else []
            if not items:
                break
            results.extend(items)
            remaining -= len(items)
            if len(items) < per_page:
                # Fewer than requested means the search has no more
                # results left - further pages would just be empty.
                break
            page += 1
        return results

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _get_comments(self, repo: str, issue_number: int) -> List[str]:
        data = self._get_json(f"{_API_BASE}/repos/{repo}/issues/{issue_number}/comments", params={})
        if not isinstance(data, list):
            return []
        return [comment.get("body") or "" for comment in data]

    def _get_json(
        self,
        url: str,
        params: Dict[str, Any],
        *,
        rate_limit_message: str = _DEFAULT_RATE_LIMIT_MESSAGE,
        invalid_message: str = _DEFAULT_INVALID_MESSAGE,
    ) -> Any:
        try:
            response = requests.get(url, headers=self._headers(), params=params, timeout=_TIMEOUT_SECONDS)
        except requests.Timeout as exc:
            raise FetcherError("GitHub API request timed out.") from exc
        except requests.RequestException as exc:
            raise FetcherError(f"GitHub API request failed ({type(exc).__name__}).") from exc

        if response.status_code == 200:
            return response.json()
        if response.status_code == 401:
            raise FetcherAuthError("GitHub token is invalid.")
        if response.status_code == 403:
            raise FetcherRateLimitError(rate_limit_message)
        if response.status_code == 404:
            raise FetcherNotFoundError(f"Repository '{_repo_from_url(url)}' not found or is private.")
        if response.status_code == 422:
            raise FetcherError(invalid_message)
        raise FetcherError(f"GitHub API error: {response.status_code}")

    def _issue_to_post(self, issue: Dict[str, Any]) -> FetchedPost:
        repo = _repo_from_repository_url(issue.get("repository_url") or "")
        number = issue.get("number")
        comments = self._get_comments(repo, number) if (repo and number is not None) else []

        text = issue.get("body") or ""
        if comments:
            text = f"{text}\n\n--- Comments ---\n" + "\n".join(comments)

        reactions = issue.get("reactions") or {}
        score = int(reactions.get("+1") or 0) + int(reactions.get("heart") or 0)
        user = issue.get("user") or {}

        return FetchedPost(
            source="github",
            item_type="post",
            id=f"{repo}#{number}",
            title=issue.get("title"),
            text=text,
            author=user.get("login") or "[unknown]",
            url=issue.get("html_url", ""),
            created_at=_parse_datetime(issue.get("created_at")),
            score=score,
            is_mock=False,
            raw={"repo": repo, "number": number},
        )


def _repo_from_repository_url(url: str) -> str:
    # A Search Issues API item names its repo via "repository_url":
    # "https://api.github.com/repos/{owner}/{repo}" - extract just the
    # "owner/repo" segment (used for the comments-fetch URL and as this
    # post's id prefix).
    marker = "/repos/"
    if marker not in url:
        return ""
    return url.split(marker, 1)[1]


def _repo_from_url(url: str) -> str:
    # url looks like ".../repos/{owner}/{repo}/issues/{n}/comments" -
    # extract just the "owner/repo" segment for a readable error message.
    marker = "/repos/"
    if marker not in url:
        return url
    after = url.split(marker, 1)[1]
    parts = after.split("/")
    return "/".join(parts[:2]) if len(parts) >= 2 else after


def _parse_datetime(value: Optional[str]) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
