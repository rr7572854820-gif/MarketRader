"""Real Reddit fetcher, read-only, via PRAW.

Only constructed by the factory (src/fetchers/__init__.py) when
config.reddit_configured is True. Nothing in here should be imported
directly by pipeline code — see src/fetchers/base.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List

from src.config import Config
from src.fetchers.base import Fetcher, FetcherError
from src.models import FetchedPost, FetchQuery


class RedditFetcher(Fetcher):
    """Fetches posts and their top-level comments from a single subreddit."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def fetch(self, query: FetchQuery) -> List[FetchedPost]:
        """Fetch recent posts (optionally keyword-filtered) from
        query.community, plus each post's top-level comments.

        Raises:
            FetcherError: On any authentication or API failure. The
                underlying praw/prawcore exception is never exposed
                directly to the caller, and its message is never
                included — only its exception type name — since
                error messages from these libraries can echo request
                details we don't want to risk surfacing.
        """
        import praw
        import prawcore

        try:
            reddit = praw.Reddit(
                client_id=self._config.reddit_client_id,
                client_secret=self._config.reddit_client_secret,
                user_agent=self._config.reddit_user_agent,
            )
            reddit.read_only = True

            subreddit = reddit.subreddit(query.community)
            if query.keyword:
                submissions = subreddit.search(query.keyword, limit=query.limit)
            else:
                submissions = subreddit.new(limit=query.limit)

            posts: List[FetchedPost] = []
            for submission in submissions:
                posts.append(_submission_to_post(submission))
                posts.extend(_top_level_comments(submission))
            return posts

        except (prawcore.exceptions.OAuthException, prawcore.exceptions.ResponseException) as exc:
            raise FetcherError(f"Reddit authentication/API error ({type(exc).__name__})") from exc
        except FetcherError:
            raise
        except Exception as exc:
            raise FetcherError(f"Reddit fetch failed unexpectedly ({type(exc).__name__})") from exc


def _top_level_comments(submission: Any) -> List[FetchedPost]:
    submission.comments.replace_more(limit=0)
    return [
        _comment_to_post(comment)
        for comment in submission.comments.list()
        if comment.parent_id == submission.name
    ]


def _submission_to_post(submission: Any) -> FetchedPost:
    return FetchedPost(
        source="reddit",
        item_type="post",
        id=submission.id,
        title=submission.title,
        text=submission.selftext or "",
        author=str(submission.author) if submission.author else "[deleted]",
        url=f"https://www.reddit.com{submission.permalink}",
        created_at=datetime.fromtimestamp(submission.created_utc, tz=timezone.utc),
        score=submission.score,
        is_mock=False,
        raw={"num_comments": submission.num_comments},
    )


def _comment_to_post(comment: Any) -> FetchedPost:
    return FetchedPost(
        source="reddit",
        item_type="comment",
        id=comment.id,
        title=None,
        text=comment.body or "",
        author=str(comment.author) if comment.author else "[deleted]",
        url=f"https://www.reddit.com{comment.permalink}",
        created_at=datetime.fromtimestamp(comment.created_utc, tz=timezone.utc),
        score=comment.score,
        is_mock=False,
        raw={},
    )
