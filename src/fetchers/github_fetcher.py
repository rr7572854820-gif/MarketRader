"""Real GitHub Issues fetcher, read-only, via the GitHub REST API.

Only constructed by the factory (src/fetchers/__init__.py) when explicitly
selected via get_fetcher(config, source="github") - unlike Reddit, there's
no config flag that makes GitHub "configured" or not. GITHUB_TOKEN is
optional and only affects rate limits (60/hour public vs 5000/hour
authenticated).

Repo discovery: this fetcher no longer takes an explicit repo. A user
supplies only a topic keyword (e.g. "invoicing"), and discover_repos()
finds up to _MAX_DISCOVERED_REPOS candidate public repositories via
GitHub's Search API, filtering out archived repos, forks, and repos with
zero open issues (nothing to fetch). This replaced an earlier, simpler
design where the caller supplied "owner/repo" directly - removed because
requiring the user to already know the exact repo defeats the point of a
market-intelligence tool that's supposed to find where to look, not
assume the user already knows.

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
_MAX_DISCOVERED_REPOS = 5

_DEFAULT_RATE_LIMIT_MESSAGE = "GitHub rate limit exceeded. Add GITHUB_TOKEN to .env for higher limits."
_DEFAULT_INVALID_MESSAGE = "Invalid repository format. Use 'owner/repo'."


class GitHubFetcher(Fetcher):
    """Discovers relevant public repos for a keyword, then fetches open
    issues (plus their comments) from each.

    query.community is not used - discovery is driven entirely by
    query.keyword as the GitHub Search API query (see discover_repos).
    A keyword is therefore required, not optional, for this fetcher
    specifically - there is no other way to know which repos to look at.

    Unlike MockFetcher, fetch() does not re-apply keyword as a manual
    substring filter on individual issues afterward - the same
    precedent RedditFetcher already set (it delegates keyword relevance
    to subreddit.search() rather than filtering fetched posts itself).
    An earlier version did re-filter here; live-tested and reverted
    after confirming it dropped genuinely relevant issues from
    correctly-discovered repos (e.g. an "invoicing" search surfaced
    invoiceninja/invoiceninja and akaunting/akaunting - real invoicing
    tools - but their actual issue titles/bodies, like "Fix PDF
    export," don't repeat the word "invoicing," so every single result
    was filtered out). Repo-level relevance from discover_repos's
    Search API query is the real filter; an issue's own text doesn't
    need to repeat the search term to be in-scope.

    Each issue becomes exactly one FetchedPost (item_type="post"); its
    comments are appended into that same post's text rather than
    becoming their own FetchedPost items - the same simplification as
    before repo discovery was added, see TODO.md.
    """

    def __init__(self, config: Config) -> None:
        self._token = config.github_token

    def fetch(self, query: FetchQuery) -> List[FetchedPost]:
        """Discover up to _MAX_DISCOVERED_REPOS repos for query.keyword
        and fetch open issues (with comments folded in) from each.

        Raises:
            FetcherError: If query.keyword is missing/blank, if no
                repository survives discovery's filtering, if every
                discovered repo's issue fetch fails, or on a search-API
                failure (see discover_repos).
        """
        if not query.keyword:
            raise FetcherError("A keyword is required to discover GitHub repositories.")

        repos = self.discover_repos(query.keyword, max_repos=_MAX_DISCOVERED_REPOS)
        per_repo_limit = max(1, query.limit // len(repos))

        posts: List[FetchedPost] = []
        fetched_any = False
        for repo in repos:
            try:
                issues = self._get_issues(repo, per_repo_limit)
            except FetcherError as exc:
                logger.warning("Skipping GitHub repo %r after fetch failure: %s", repo, exc)
                continue
            fetched_any = True
            posts.extend(self._issue_to_post(repo, issue) for issue in issues)

        if not fetched_any:
            raise FetcherError("Could not fetch issues from any discovered repository.")

        return posts

    def discover_repos(self, keyword: str, max_repos: int = _MAX_DISCOVERED_REPOS) -> List[str]:
        """Finds up to max_repos active, non-archived, non-fork public
        repos matching keyword via GitHub's Search API, ranked by stars.

        The search itself only requests max_repos candidates (per_page),
        so a candidate pool with archived/fork/no-issue repos among it
        can return fewer than max_repos after filtering - a known,
        accepted limitation (see architecture review), not a bug.

        Raises:
            FetcherRateLimitError: The search API's own rate limit was
                hit (403).
            FetcherError: The search keyword was rejected (422), or zero
                repos survive filtering.
        """
        data = self._get_json(
            f"{_API_BASE}/search/repositories",
            params={
                "q": f"{keyword} in:name,description,topics",
                "sort": "stars",
                "order": "desc",
                "per_page": max_repos,
            },
            rate_limit_message="GitHub search rate limit exceeded.",
            invalid_message="Invalid search keyword.",
        )
        items = data.get("items", []) if isinstance(data, dict) else []
        repos = [
            item["full_name"]
            for item in items
            if isinstance(item, dict)
            and item.get("full_name")
            and not item.get("archived")
            and not item.get("fork")
            and item.get("open_issues_count")
        ][:max_repos]

        if not repos:
            raise FetcherError(f"No active public repositories found for '{keyword}'.")
        return repos

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _get_issues(self, repo: str, per_page: int) -> List[Dict[str, Any]]:
        per_page = max(1, min(per_page, _MAX_PER_PAGE))
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
