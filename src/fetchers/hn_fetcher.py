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
# Lowered from 5 (live-verified: at >5, a real "invoicing" search
# returned very few - sometimes zero - quality-passing hits; Hacker
# News stories in general have a much lower typical point count than
# the threshold assumed, and >1 still excludes the near-zero-signal
# tail while letting real, on-topic discussion through).
_MIN_POINTS = 1

_HIRING_MARKERS = ("who is hiring", "ask hn: who")
_POLL_MARKER = "poll:"


class HNFetcher(BaseFetcher):
    """Searches Hacker News stories directly via the Algolia HN Search
    API, preferring query.original_keyword over query.keyword/keywords
    (see fetch()'s own docstring for why), then applies a quality
    filter (points, hiring/poll noise) only - no post-fetch keyword-
    presence re-check (removed; see fetch()'s own docstring for why).

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
        """Search Hacker News stories for query.original_keyword (falling
        back to query.keyword when unset - see FetchQuery's own
        docstring).

        Deliberately searches the user's original, pre-expansion input
        rather than query.keyword/keywords whenever QueryExpander has
        run (source="github"/"all" - src/pipeline/pipeline.py): those
        are AI-expanded, technical-sounding terms tuned for GitHub's
        Search Issues API specifically (e.g. "api gateway architecture"
        for a user who typed "api"), and Algolia's own search - live-
        verified - returns far fewer, sometimes zero, results for a
        long, specific technical phrase than for the short, broad term
        a real HN discussion's title is actually likely to contain.

        Raises:
            FetcherError: If no keyword is available at all, the
                Algolia API times out, or returns a non-200 status.
                Zero matching stories is not an error - returns [].
        """
        search_term = query.original_keyword or query.keyword
        if not search_term:
            raise FetcherError("A keyword is required to search Hacker News.")

        limit = max(1, query.limit)
        hits_per_page = min(limit * _OVERSAMPLE_MULTIPLIER, _MAX_HITS_PER_PAGE)

        hits = self._search_stories(search_term, hits_per_page)

        # No post-fetch keyword-presence filter here (unlike an earlier
        # version of this method) - live-verified to remove too many
        # real, on-topic results: Algolia's own search relevance is
        # already the actual filter (the same lesson GitHubFetcher
        # learned and removed its own equivalent post-fetch filter for -
        # see that module's docstring), and a broad, single-word search
        # term (see above) makes a literal substring re-check even more
        # likely to reject a genuinely relevant story that just doesn't
        # happen to repeat the exact search word in its title/body.
        posts: List[FetchedPost] = []
        for hit in hits:
            if not self._passes_quality_filter(hit):
                continue
            posts.append(self._hit_to_post(hit))
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
