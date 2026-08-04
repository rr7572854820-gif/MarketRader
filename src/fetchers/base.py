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

import logging
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, List, Optional

from src.models import FetchedPost, FetchQuery

logger = logging.getLogger(__name__)


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


class BaseFetcher(Fetcher):
    """Base class all fetchers should inherit.

    Provides parallel fetching and content truncation automatically.
    New fetchers inherit this instead of raw Fetcher to get speed
    improvements free. Existing fetchers migrate gradually. Nothing
    breaks if they don't migrate.

    Still abstract: this class does not implement fetch() itself, so
    it cannot be instantiated directly — a subclass must still provide
    fetch(), exactly as it would under plain Fetcher. Only two new
    helper methods are added on top; nothing about the Fetcher
    interface itself changes for any existing caller.

    Addresses a named, previously-accepted gap (see
    ENGINEERING_GUIDE.md's Performance Guidelines / TODO.md): fetchers
    have made sequential, synchronous HTTP calls with no parallelism
    and no content-size bound — fetch_parallel() and truncate_content()
    exist so a fetcher that opts in can fix both, without every fetcher
    being forced to at once.
    """

    MAX_WORKERS: int = 5
    MAX_CONTENT_LENGTH: int = 1500
    FETCH_TIMEOUT: int = 10

    def truncate_content(self, content: str) -> str:
        """Caps content to MAX_CONTENT_LENGTH characters, appending a
        visible marker when truncated so callers never mistake a cut
        string for the complete original text.
        """
        if not content:
            return content or ""
        if len(content) <= self.MAX_CONTENT_LENGTH:
            return content
        return content[: self.MAX_CONTENT_LENGTH] + "\n\n[Content truncated for analysis]"

    def fetch_parallel(
        self,
        items: List[Any],
        fetch_fn: Callable[[Any], Any],
        max_workers: Optional[int] = None,
    ) -> List[Any]:
        """Fetches multiple items in parallel via a thread pool (fetches
        are I/O-bound HTTP calls, not CPU-bound, so threads — not
        processes — are the right tool here).

        Each item's fetch is independent: a failure fetching one item
        is logged and contributes an empty result for that item only,
        never an exception that aborts the whole batch — the same
        per-item resilience principle every other stage of this
        project already follows (e.g. Pipeline._analyze's per-post
        extraction failures).

        Args:
            items: The inputs to fetch, one call to fetch_fn per item.
            fetch_fn: Called with a single item; may return either a
                list (extended into the flattened result) or a single
                value (wrapped into a one-item list first).
            max_workers: Overrides MAX_WORKERS for this call only.

        Returns:
            A single flattened list combining every item's results, in
            the same order as `items` (ThreadPoolExecutor.map
            preserves input order regardless of completion order).
            Never raises for an individual item's failure.

        Usage in a subclass:
            results = self.fetch_parallel(repos, self._fetch_single_repo)
        """
        workers = max_workers or self.MAX_WORKERS

        def safe_fetch(item: Any) -> List[Any]:
            try:
                result = fetch_fn(item)
                return result if isinstance(result, list) else [result]
            except Exception as exc:  # noqa: BLE001 — per-item isolation is the entire point here, see docstring
                logger.warning("Fetch failed for %s: %s", item, exc)
                return []

        with ThreadPoolExecutor(max_workers=workers) as executor:
            all_results = list(executor.map(safe_fetch, items))

        return [item for sublist in all_results for item in sublist]
