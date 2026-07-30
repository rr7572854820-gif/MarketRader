"""Mock fetcher — returns a small, fixed set of clearly-labeled sample
posts instead of contacting any real source.

Used automatically by the factory (src/fetchers/__init__.py) when
config.reddit_configured is False, so the rest of the project can be
built and exercised without a Reddit account or API key.

This data is NOT evidence. Every item has is_mock=True and a
"mock://" URL that resolves nowhere. Per the project's core "never
fabricate evidence" principle (CLAUDE.md §5), nothing downstream may
ever present these items as a real finding — any report/output that
includes mock data must say so as plainly as this module does.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from src.fetchers.base import Fetcher
from src.models import FetchedPost, FetchQuery

_MOCK_POSTS: List[FetchedPost] = [
    FetchedPost(
        source="mock",
        item_type="post",
        id="mock-001",
        title="Anyone else hate reconciling Stripe payouts with QuickBooks manually every month?",
        text=(
            "I run a small subscription business and every month I spend 3-4 hours "
            "manually matching Stripe payout line items against what shows up in "
            "QuickBooks. The fees, refunds, and disputes never match cleanly and I "
            "end up in a spreadsheet at midnight. Feels like this should just be "
            "solved already."
        ),
        author="mock_user_amelia",
        url="mock://sample/post-001",
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        score=42,
        is_mock=True,
    ),
    FetchedPost(
        source="mock",
        item_type="comment",
        id="mock-002",
        title=None,
        text=(
            "Same here, except I run an agency and it's payouts across three "
            "different processors. I built a garbage internal script to do it and "
            "it still breaks every time someone issues a partial refund."
        ),
        author="mock_user_devon",
        url="mock://sample/comment-002",
        created_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
        score=18,
        is_mock=True,
    ),
    FetchedPost(
        source="mock",
        item_type="comment",
        id="mock-003",
        title=None,
        text=(
            "I actually pay a bookkeeper $200/month partly just to deal with this "
            "reconciliation mess. If there were a tool that did it automatically for "
            "under that price I'd switch immediately."
        ),
        author="mock_user_priya_k",
        url="mock://sample/comment-003",
        created_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
        score=31,
        is_mock=True,
    ),
    FetchedPost(
        source="mock",
        item_type="post",
        id="mock-004",
        title="Customer support tickets about our own onboarding flow keep repeating the same confusion",
        text=(
            "We keep getting the exact same support ticket: new users can't figure "
            "out how to invite teammates because the invite button is buried in a "
            "settings submenu. It's like 1 in 5 new signups files a ticket about "
            "this specific thing."
        ),
        author="mock_user_frankie",
        url="mock://sample/post-004",
        created_at=datetime(2026, 6, 5, tzinfo=timezone.utc),
        score=9,
        is_mock=True,
    ),
    FetchedPost(
        source="mock",
        item_type="post",
        id="mock-005",
        title="Every no-code tool I've tried breaks the moment I need conditional logic",
        text=(
            "I've tried three different no-code form builders this year and all of "
            "them fall apart once I need more than one level of conditional "
            "branching. I keep having to hire a dev to bolt on custom JS, which "
            "defeats the whole point of no-code."
        ),
        author="mock_user_sana",
        url="mock://sample/post-005",
        created_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
        score=27,
        is_mock=True,
    ),
    FetchedPost(
        source="mock",
        item_type="comment",
        id="mock-006",
        title=None,
        text=(
            "This 100%. I switched tools twice for this exact reason and ended up "
            "back on spreadsheets + Zapier, which is somehow more reliable than "
            "either 'no-code' product I paid for."
        ),
        author="mock_user_leo_t",
        url="mock://sample/comment-006",
        created_at=datetime(2026, 6, 9, tzinfo=timezone.utc),
        score=14,
        is_mock=True,
    ),
    FetchedPost(
        source="mock",
        item_type="post",
        id="mock-007",
        title="Every meeting scheduler I've used fails the moment a client is in a different timezone",
        text=(
            "I've tried Calendly, Cal.com, and two others. All of them mostly work "
            "until a client books from a timezone with a weird DST offset, and then "
            "I show up an hour off at least once a quarter. I've started just "
            "asking clients to say the time in my own timezone, which defeats the "
            "point of using a scheduler at all."
        ),
        author="mock_user_tobias",
        url="mock://sample/post-007",
        created_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
        score=22,
        is_mock=True,
    ),
]


class MockFetcher(Fetcher):
    """Returns items from the fixed sample dataset above, optionally
    keyword-filtered and limited, ignoring query.community — there's no
    real subreddit behind mock data, so there's nothing to select by.
    """

    def fetch(self, query: FetchQuery) -> List[FetchedPost]:
        posts = _MOCK_POSTS
        if query.keyword:
            keyword = query.keyword.lower()
            posts = [
                post
                for post in posts
                if keyword in post.text.lower()
                or (post.title is not None and keyword in post.title.lower())
            ]
        return list(posts[: query.limit])
