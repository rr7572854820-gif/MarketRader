"""Task 2 verification command.

Fetches posts — real Reddit data or mock sample data, chosen
automatically from config.reddit_configured — and prints them so you
can confirm the fetcher works. Does not extract, verify, group, or
write a report; that's later tasks.

Run from the project root:
    python -m src.fetch_preview SOME_SUBREDDIT
    python -m src.fetch_preview SOME_SUBREDDIT --keyword refund --limit 10

In mock mode, the community argument is still required but ignored
(there's no real subreddit behind the sample data) — any value works,
e.g. `python -m src.fetch_preview mock`.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from src.config import load_config
from src.fetchers import Fetcher, FetcherError, get_fetcher
from src.models import FetchedPost, FetchQuery


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and print posts (Task 2 preview).")
    parser.add_argument(
        "community",
        help="Subreddit name. Ignored in mock mode, but still required.",
    )
    parser.add_argument("--keyword", default=None, help="Optional keyword filter.")
    parser.add_argument("--limit", type=int, default=25, help="Max posts to fetch.")
    return parser.parse_args(argv)


def _print_post(index: int, post: FetchedPost) -> None:
    label = "[MOCK]" if post.is_mock else "[REAL]"
    print(f"{label} #{index} - {post.item_type} - source={post.source}")
    if post.title:
        print(f"  Title:   {post.title}")
    print(f"  Author:  {post.author}")
    print(f"  URL:     {post.url}")
    print(f"  Created: {post.created_at.isoformat()}")
    if post.score is not None:
        print(f"  Score:   {post.score}")
    text_preview = post.text.strip().replace("\n", " ")
    if len(text_preview) > 200:
        text_preview = text_preview[:200] + "..."
    print(f"  Text:    {text_preview}")
    print()


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    config = load_config()
    fetcher: Fetcher = get_fetcher(config)
    mode = "REAL Reddit data" if config.reddit_configured else "MOCK sample data"
    print(f"Fetching using: {mode}\n")

    query = FetchQuery(community=args.community, keyword=args.keyword, limit=args.limit)

    try:
        posts = fetcher.fetch(query)
    except FetcherError as exc:
        print(f"[FAIL] Fetch failed: {exc}")
        return 1

    if not posts:
        print("No posts returned.")
        return 0

    for index, post in enumerate(posts, start=1):
        _print_post(index, post)

    print(f"Total: {len(posts)} item(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
