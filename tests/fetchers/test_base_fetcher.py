"""Tests for src/fetchers/base.py's BaseFetcher: truncate_content() and
fetch_parallel(). BaseFetcher itself stays abstract (fetch() is not
implemented), so tests instantiate a minimal concrete subclass rather
than BaseFetcher directly - the same pattern any real fetcher migrating
onto it would follow.
"""

from __future__ import annotations

from typing import List

import pytest

from src.fetchers.base import BaseFetcher, Fetcher
from src.models import FetchedPost, FetchQuery


class _ConcreteFetcher(BaseFetcher):
    """Minimal concrete subclass - fetch() is never exercised by these
    tests (they call truncate_content/fetch_parallel directly), but
    BaseFetcher can't be instantiated without it since fetch() stays
    abstract on Fetcher.
    """

    def fetch(self, query: FetchQuery) -> List[FetchedPost]:
        raise NotImplementedError


@pytest.fixture
def fetcher() -> _ConcreteFetcher:
    return _ConcreteFetcher()


# --- truncate_content ----------------------------------------------------------------


def test_truncate_long_content(fetcher: _ConcreteFetcher):
    content = "x" * 3000
    result = fetcher.truncate_content(content)

    assert len(result) <= 1600
    assert "[Content truncated for analysis]" in result


def test_truncate_short_content(fetcher: _ConcreteFetcher):
    content = "x" * 500
    result = fetcher.truncate_content(content)

    assert result == content


def test_truncate_empty_content(fetcher: _ConcreteFetcher):
    assert fetcher.truncate_content("") == ""
    assert fetcher.truncate_content(None) == ""  # must not crash


# --- fetch_parallel --------------------------------------------------------------------


def test_fetch_parallel_all_succeed(fetcher: _ConcreteFetcher):
    def fetch_fn(item):
        return [item]

    results = fetcher.fetch_parallel([1, 2, 3], fetch_fn)

    assert sorted(results) == [1, 2, 3]


def test_fetch_parallel_one_fails(fetcher: _ConcreteFetcher):
    def fetch_fn(item):
        if item == 1:
            raise ValueError("simulated failure")
        return [item]

    results = fetcher.fetch_parallel([1, 2, 3], fetch_fn)  # must not raise

    assert sorted(results) == [2, 3]


def test_fetch_parallel_all_fail(fetcher: _ConcreteFetcher):
    def fetch_fn(item):
        raise ValueError("simulated failure")

    results = fetcher.fetch_parallel([1, 2, 3], fetch_fn)  # must not raise

    assert results == []


# --- Interface -----------------------------------------------------------------------


def test_base_fetcher_inherits_fetcher():
    assert issubclass(BaseFetcher, Fetcher)
