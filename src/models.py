"""Source-agnostic data shapes shared by every fetcher and, later, every
pipeline stage (extractor, verifier, grouper, report writer). Nothing
downstream of the fetcher layer should ever import a source-specific
type (a PRAW Submission, a future HN/GitHub API object, etc.) — only
FetchedPost. That's what lets a new source be added without touching
the analysis pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class FetchedPost:
    """One unit of raw source content — a post or a top-level comment —
    in a shape that's identical regardless of where it came from.

    Attributes:
        source: Short source identifier, e.g. "reddit", "mock", and
            later "hackernews", "producthunt", "github".
        item_type: "post" or "comment".
        id: Source-specific unique identifier for this item.
        title: Title text, if the source has one (posts usually do,
            comments usually don't — None when not applicable).
        text: The actual body text. This is the only field later
            pipeline stages are allowed to quote from.
        author: Pseudonymous author identifier as given by the source.
        url: Direct, dereferenceable permalink back to the source item.
            Mandatory and must never be empty — this is the evidence
            trail the whole project depends on.
        created_at: When the item was originally posted, timezone-aware.
        score: Upvotes/points if the source has a concept of one.
        is_mock: True only for dummy/sample data. Must be checked by any
            code that presents findings as real evidence — mock data
            must never be shown as if it were a genuine finding.
        raw: Source-specific extra fields, kept for debugging only.
            Never rely on anything in here from generic pipeline code.
    """

    source: str
    item_type: str
    id: str
    title: Optional[str]
    text: str
    author: str
    url: str
    created_at: datetime
    score: Optional[int] = None
    is_mock: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FetchQuery:
    """A source-agnostic request for data.

    Attributes:
        community: Which community/board to fetch from. For Reddit this
            is a subreddit name. Future sources may interpret it
            differently (e.g. a repo name for GitHub) or ignore it
            (e.g. mock data).
        keyword: Optional keyword filter. The single, primary term -
            always set alongside keywords when there are several (e.g.
            keywords[0]), so any fetcher that only understands keyword
            still behaves exactly as before.
        keywords: Optional list of related search terms (e.g. from
            src.search.query_expander.QueryExpander), for a fetcher
            that can search each one separately and merge the results -
            currently only GitHubFetcher does. None/empty means "use
            keyword alone" - every existing call site that never sets
            this keeps working unchanged.
        limit: Maximum number of posts to return.
    """

    community: str
    keyword: Optional[str] = None
    keywords: Optional[List[str]] = None
    limit: int = 25
