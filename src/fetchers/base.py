"""The Fetcher interface every data source must implement.

Nothing outside this package should import a concrete fetcher
(RedditFetcher, MockFetcher, or any future HackerNewsFetcher /
ProductHuntFetcher / GitHubFetcher) directly. Everything else — the
analysis pipeline, CLI commands, tests — should depend only on this
interface, on FetcherError, and on src.models.FetchedPost. Adding a new
source later means adding one new class here and one line in the
factory (src/fetchers/__init__.py); it should never require touching
code that consumes fetched data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from src.models import FetchedPost, FetchQuery


class FetcherError(Exception):
    """Raised by any Fetcher implementation when a fetch fails.

    Callers should catch this one type and never a source-specific
    exception (e.g. a prawcore exception) — that's what keeps calling
    code source-agnostic.
    """


class Fetcher(ABC):
    """Common interface for pulling posts/comments from a single source."""

    @abstractmethod
    def fetch(self, query: FetchQuery) -> List[FetchedPost]:
        """Fetch posts/comments matching query.

        Args:
            query: What to fetch (community, optional keyword, limit).

        Returns:
            A list of FetchedPost, in the shared source-agnostic shape.
            May be empty if nothing matched — that is not an error.

        Raises:
            FetcherError: If the fetch could not be completed (auth
                failure, network error, source unavailable, etc.).
                Implementations must translate any source-specific
                exception into a FetcherError rather than letting it
                propagate directly.
        """
        raise NotImplementedError
