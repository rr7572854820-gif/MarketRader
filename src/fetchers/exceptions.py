"""GitHub-specific FetcherError subclasses.

These exist as subclasses of FetcherError (src/fetchers/base.py), not a
parallel hierarchy - base.py's own documented rule is that calling code
should "catch this one type and never a source-specific exception," and
subclassing preserves that: `except FetcherError` still catches every
GitHub failure exactly as it catches Reddit's. The more specific types
exist only so GitHubFetcher's own tests (and any future caller that
genuinely needs to distinguish "bad token" from "repo not found") can
be precise about *why* a fetch failed, without weakening the
source-agnostic guarantee everything else in this project relies on.

Only src/fetchers/github_fetcher.py raises these.
"""

from __future__ import annotations

from src.fetchers.base import FetcherError


class FetcherAuthError(FetcherError):
    """Raised when the configured credential/token is invalid or rejected."""


class FetcherRateLimitError(FetcherError):
    """Raised when the source's rate limit has been exceeded."""


class FetcherNotFoundError(FetcherError):
    """Raised when the requested resource (e.g. a repo) doesn't exist or isn't accessible."""
