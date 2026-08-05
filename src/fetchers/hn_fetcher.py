"""Real Hacker News fetcher, read-only, via the Algolia HN Search API.

No API key or credential of any kind - Algolia's HN index
(hn.algolia.com/api/v1/search) is public and unauthenticated, unlike
GitHubFetcher's optional GITHUB_TOKEN. HNFetcher still takes a Config
in its constructor (matching RedditFetcher/GitHubFetcher's shape, for
factory uniformity - src/fetchers/__init__.py always calls a real
fetcher as FetcherClass(config)) even though nothing in Config is
actually read.

Search strategy: one Algolia search call per fetch() (tags=story, so
comments never come back), oversampling via hitsPerPage (limit * 3, up
to Algolia's own 100-per-page ceiling) before a quality filter removes
low-signal/hiring/poll noise - the same "fetch a wider pool, filter
down" shape GitHubFetcher's Search Issues call uses, just without
pagination (Algolia's single page is already wide enough for this
project's limit sizes; adding a paging loop here would be speculative
complexity with no current use).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from src.config import Config
from src.fetchers.base import BaseFetcher, FetcherError
from src.models import FetchedPost, FetchQuery

logger = logging.getLogger(__name__)

_API_BASE = "https://hn.algolia.com/api/v1/search"
_TIMEOUT_SECONDS = 10
_MAX_HITS_PER_PAGE = 100
_OVERSAMPLE_MULTIPLIER = 3
_MIN_POINTS = 5

_HIRING_MARKERS = ("who is hiring", "ask hn: who")
_POLL_MARKER = "poll:"


class HNFetcher(BaseFetcher):
    """Searches Hacker News stories directly for query.keyword via the
    Algolia HN Search API, applies a quality filter (points, hiring/poll
    noise), then a keyword-presence filter against the fetched title/body
    text - the same two-stage "wide search, then filter" shape
    GitHubFetcher's Search Issues call plus RelevanceRanker uses,
    adapted to what Algolia's response actually returns (points/
    num_comments in place of GitHub's reactions/comment-count).

    query.community is not used - Hacker News has no equivalent concept
    (see FetchQuery's own docstring: fetchers are free to ignore fields
    that don't apply to their source). A keyword is required, not
    optional - it is the entire Algolia search query, same convention
    as GitHubFetcher.

    Each story becomes exactly one FetchedPost (item_type="post"); HN
    comments are not fetched at all (Algolia's `tags=story` filter
    already excludes them, and per-story comment threads would need a
    separate API call per story - out of this task's scope, unlike
    GitHubFetcher's per-issue comments call, which this class does not
    replicate).

    Inherits BaseFetcher (src/fetchers/base.py) only for
    truncate_content() - there is no per-item HTTP call to parallelize
    here (fetch() makes exactly one Algolia request total), unlike
    GitHubFetcher's per-issue comments fetch.
    """

    def __init__(self, config: Config) -> None:
        pass

    def fetch(self, query: FetchQuery) -> List[FetchedPost]:
        """Search Hacker News stories for query.keyword.

        Raises:
            FetcherError: If query.keyword is missing/blank, the
                Algolia API times out, or returns a non-200 status.
                Zero matching stories is not an error - returns [].
        """
        if not query.keyword:
            raise FetcherError("A keyword is required to search Hacker News.")

        limit = max(1, query.limit)
        hits_per_page = min(limit * _OVERSAMPLE_MULTIPLIER, _MAX_HITS_PER_PAGE)

        hits = self._search_stories(query.keyword, hits_per_page)

        keyword_lower = query.keyword.lower()
        posts: List[FetchedPost] = []
        for hit in hits:
            if not self._passes_quality_filter(hit):
                continue
            post = self._hit_to_post(hit)
            if keyword_lower not in post.title.lower() and keyword_lower not in post.text.lower():
                continue
            posts.append(post)
            if len(posts) >= limit:
                break

        return posts

    def _search_stories(self, keyword: str, hits_per_page: int) -> List[Dict[str, Any]]:
        try:
            response = requests.get(
                _API_BASE,
                params={
                    "query": keyword,
                    "tags": "story",
                    "hitsPerPage": hits_per_page,
                    "numericFilters": f"points>{_MIN_POINTS}",
                },
                timeout=_TIMEOUT_SECONDS,
            )
        except requests.Timeout as exc:
            raise FetcherError("HackerNews API timed out.") from exc
        except requests.RequestException as exc:
            raise FetcherError(f"HackerNews API request failed ({type(exc).__name__}).") from exc

        if response.status_code != 200:
            raise FetcherError(f"HackerNews returned {response.status_code}")

        data = response.json()
        return data.get("hits", []) if isinstance(data, dict) else []

    def _passes_quality_filter(self, hit: Dict[str, Any]) -> bool:
        title = hit.get("title")
        if title is None:
            return False
        points = hit.get("points")
        if points is None or points < _MIN_POINTS:
            return False
        title_lower = title.lower()
        if any(marker in title_lower for marker in _HIRING_MARKERS):
            return False
        if _POLL_MARKER in title_lower:
            return False
        return True

    def _hit_to_post(self, hit: Dict[str, Any]) -> FetchedPost:
        object_id = hit.get("objectID", "")
        title = hit.get("title") or ""
        body = hit.get("story_text") or f"HN Discussion: {title}"
        body = self.truncate_content(body)

        return FetchedPost(
            source="hackernews",
            item_type="post",
            id=str(object_id),
            title=title,
            text=body,
            author=hit.get("author") or "[unknown]",
            url=f"https://news.ycombinator.com/item?id={object_id}",
            created_at=_parse_datetime(hit.get("created_at")),
            score=hit.get("points"),
            is_mock=False,
            raw={"num_comments": hit.get("num_comments"), "external_url": hit.get("url")},
        )


def _parse_datetime(value: Optional[str]) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
