"""Real GitHub Issues fetcher, read-only, via the GitHub REST API.

Only constructed by the factory (src/fetchers/__init__.py) when explicitly
selected via get_fetcher(config, source="github") - unlike Reddit, there's
no config flag that makes GitHub "configured" or not, since a repo name is
always required as query input, not a credential. GITHUB_TOKEN is optional
and only affects rate limits (60/hour public vs 5000/hour authenticated).

Nothing in here should be imported directly by pipeline code - see
src/fetchers/base.py.
"""

from __future__ import annotations

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

_API_BASE = "https://api.github.com"
_TIMEOUT_SECONDS = 10
_MAX_PER_PAGE = 100


class GitHubFetcher(Fetcher):
    """Fetches open issues (plus their comments) from a single GitHub repo.

    query.community is interpreted as "owner/repo" (e.g. "microsoft/vscode")
    - the same "which board to fetch from" role RedditFetcher gives a
    subreddit name, per FetchQuery's own docstring, which already
    anticipates a repo name filling this slot for a future GitHub source.

    Each issue becomes exactly one FetchedPost (item_type="post"); its
    comments are appended into that same post's text rather than becoming
    their own FetchedPost items the way RedditFetcher gives each top-level
    comment its own entry. GitHub issue comments don't carry the same
    per-comment score/author-as-independent-evidence structure Reddit
    comments do for this project's purposes; folding them into the parent
    issue's text is a deliberate simplification, not an oversight - see
    TODO.md for revisiting this if issue-level vs. comment-level evidence
    granularity ever turns out to matter.
    """

    def __init__(self, config: Config) -> None:
        self._token = config.github_token

    def fetch(self, query: FetchQuery) -> List[FetchedPost]:
        """Fetch open issues (with comments folded in) from query.community.

        Raises:
            FetcherAuthError: The configured GITHUB_TOKEN was rejected (401).
            FetcherRateLimitError: GitHub's rate limit was hit (403).
            FetcherNotFoundError: The repo doesn't exist or isn't accessible (404).
            FetcherError: Any other API error, malformed repo format (422),
                a request timeout, or a network failure.
        """
        repo = query.community
        per_page = max(1, min(query.limit, _MAX_PER_PAGE))

        issues = self._get_issues(repo, per_page)
        posts = [self._issue_to_post(repo, issue) for issue in issues]

        if query.keyword:
            keyword = query.keyword.lower()
            posts = [
                post
                for post in posts
                if keyword in post.text.lower() or (post.title is not None and keyword in post.title.lower())
            ]
        return posts

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _get_issues(self, repo: str, per_page: int) -> List[Dict[str, Any]]:
        data = self._get_json(
            f"{_API_BASE}/repos/{repo}/issues",
            params={"state": "open", "per_page": per_page, "page": 1, "sort": "created", "direction": "desc"},
        )
        return data if isinstance(data, list) else []

    def _get_comments(self, repo: str, issue_number: int) -> List[str]:
        data = self._get_json(f"{_API_BASE}/repos/{repo}/issues/{issue_number}/comments", params={})
        if not isinstance(data, list):
            return []
        return [comment.get("body") or "" for comment in data]

    def _get_json(self, url: str, params: Dict[str, Any]) -> Any:
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
            raise FetcherRateLimitError(
                "GitHub rate limit exceeded. Add GITHUB_TOKEN to .env for higher limits."
            )
        if response.status_code == 404:
            raise FetcherNotFoundError(f"Repository '{_repo_from_url(url)}' not found or is private.")
        if response.status_code == 422:
            raise FetcherError("Invalid repository format. Use 'owner/repo'.")
        raise FetcherError(f"GitHub API error: {response.status_code}")

    def _issue_to_post(self, repo: str, issue: Dict[str, Any]) -> FetchedPost:
        number = issue.get("number")
        comments = self._get_comments(repo, number) if number is not None else []

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


def _repo_from_url(url: str) -> str:
    # url looks like ".../repos/{owner}/{repo}/issues" or ".../comments" -
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
