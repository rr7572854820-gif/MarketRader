"""Universal relevance scoring, plus a GitHub-issue-specific adaptation.

score_github_repo()/rank_github_repos()/score_hn_post() operate on repo-
or post-shaped dicts carrying real popularity metadata (stars, forks,
topics, points) - the class's own documented extension pattern ("Adding
a new source: add score_{source}()/rank_{source}()"). They're built here
exactly as specified and are a genuinely source-agnostic utility - not
dead code even though score_hn_post() has no caller yet (no HNFetcher
exists), because HN's own docstring names it as "ready for when HNFetcher
is added" - the same explicit forward-declaration pattern already used
by src/fetchers/base.py's BaseFetcher for fetchers not yet migrated onto
it.

score_github_issue()/rank_github_issues() are NOT part of that given
spec - they exist because src/fetchers/github_fetcher.py has no repo
objects to score at all. GitHubFetcher searches GitHub's Search Issues
API directly (see its own module docstring for why: a repo-discovery
step that filtered by repo name/description/topics was tried and
reverted, because a problem-description keyword like "invoice
automation" rarely appears in a repo's own metadata even when that
repo's issues genuinely discuss it). Issue objects from that API don't
carry stargazers_count/forks_count/topics at all - fetching them would
mean a new GET /repos/{owner}/{repo} call per unique repo encountered,
re-introducing exactly the repo-level filtering this codebase already
found drops real, relevant results. score_github_issue() scores what's
actually available on an issue (reactions, comment count, keyword match)
instead, and - unlike score_github_repo() - never hard-rejects on low
engagement: GitHub's own Search Issues relevance ordering is already
this fetcher's primary relevance signal (see github_fetcher.py), so a
quiet-but-genuinely-relevant issue must not be dropped for lacking
reactions. Only EXCLUDE_TERMS matches (tutorial/intern/practice content)
are ever excluded.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class RelevanceRanker:
    """
    Universal relevance scoring system.

    Adding new source in future:
    1. Add score_{source}() method
    2. Add rank_{source}() method
    Core ranking logic never changes.
    Takes 10 minutes per new source.
    """

    # Always exclude these repo types
    # regardless of search keyword
    EXCLUDE_TERMS = [
        "intern", "internship", "tutorial",
        "learning", "course", "homework",
        "bootcamp", "student", "practice",
        "training", "onboarding", "beginner",
        "my-first", "demo-repo", "sample-repo",
        "test-repo", "playground", "exercise",
        "workshop", "assignment", "hello-world",
        "getting-started", "learn-", "-learn",
        "focusbear", "emily-intern",
        "caroline-intern",
    ]

    def _is_excluded_text(self, searchable: str) -> bool:
        """Shared EXCLUDE_TERMS check - the one place both the repo-level
        and issue-level exclusion checks look for tutorial/intern/practice
        content, so the term list only ever needs updating in one place.

        Plain terms (no hyphen) match on a word boundary, not a bare
        substring - found via a real live GitHub search during this
        task's own verification: a naive `"intern" in text` check
        wrongly excluded 3 of 5 genuinely relevant real issues because
        their body text said "...module's internals...". Hyphenated
        terms ("learn-", "-learn", "my-first") are deliberately left as
        plain substring matches - they're fragments meant to match
        inside a compound repo-name-style token (e.g. "learn-python"),
        not whole words, so a word-boundary regex would break them.
        """
        for term in self.EXCLUDE_TERMS:
            if "-" in term:
                if term in searchable:
                    return True
            elif re.search(rf"\b{re.escape(term)}\b", searchable):
                return True
        return False

    def _is_excluded(self, repo: Dict[str, Any]) -> bool:
        """Check if repo should always be excluded."""
        name = repo.get("full_name", "").lower()
        desc = (repo.get("description") or "").lower()
        searchable = name + " " + desc

        return self._is_excluded_text(searchable)

    def score_github_repo(self, repo: Dict[str, Any], keyword: str) -> float:
        """
        Score a GitHub repo 0-100.
        Returns 0.0 for excluded repos.
        Higher = more relevant.
        """

        # Hard exclude bad repos
        if self._is_excluded(repo):
            return 0.0

        name = repo.get("full_name", "").lower()
        desc = (repo.get("description") or "").lower()
        topics = " ".join(repo.get("topics", [])).lower()
        searchable = name + " " + desc + " " + topics

        score = 0.0

        # Stars: popularity signal (0-30 pts)
        stars = repo.get("stargazers_count", 0)
        if stars >= 1000:
            score += 30
        elif stars >= 100:
            score += 20
        elif stars >= 10:
            score += 10
        elif stars >= 5:
            score += 5
        else:
            return 0.0  # less than 5 stars = skip

        # Open issues: has complaints (0-20 pts)
        issues = repo.get("open_issues_count", 0)
        if issues >= 50:
            score += 20
        elif issues >= 10:
            score += 15
        elif issues >= 3:
            score += 10
        elif issues == 0:
            return 0.0  # no issues = skip

        # Keyword match in name/desc/topics (0-30 pts)
        words = [w for w in keyword.lower().split() if len(w) > 3]
        matches = sum(1 for w in words if w in searchable)
        score += min(matches * 10, 30)

        # Forks: community signal (0-20 pts)
        forks = repo.get("forks_count", 0)
        if forks >= 100:
            score += 20
        elif forks >= 10:
            score += 10
        elif forks >= 2:
            score += 5

        return min(score, 100.0)

    def score_hn_post(self, post: Dict[str, Any], keyword: str) -> float:
        """
        Score HackerNews post 0-100.
        Ready for when HNFetcher is added.
        """
        score = 0.0

        points = post.get("points", 0)
        if points >= 100:
            score += 40
        elif points >= 50:
            score += 30
        elif points >= 20:
            score += 20
        elif points >= 5:
            score += 10
        else:
            return 0.0

        comments = post.get("num_comments", 0)
        if comments >= 50:
            score += 30
        elif comments >= 10:
            score += 20
        elif comments >= 2:
            score += 10

        title = post.get("title", "").lower()
        words = keyword.lower().split()
        matches = sum(1 for w in words if w in title)
        score += min(matches * 15, 30)

        return min(score, 100.0)

    def rank_github_repos(self, repos: List[Dict[str, Any]], keyword: str, top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Score, filter, and rank repos.
        Returns top N most relevant.
        Falls back to star-sorted if
        all repos score zero.
        """
        scored = [(repo, self.score_github_repo(repo, keyword)) for repo in repos]

        # Remove zero-scored repos
        valid = [(r, s) for r, s in scored if s > 0]

        if not valid:
            logger.warning(f"All {len(repos)} repos scored 0. Falling back to top 3 by stars.")
            fallback = sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)
            return fallback[:3]

        valid.sort(key=lambda x: x[1], reverse=True)

        result = [r for r, s in valid[:top_n]]
        logger.info(f"Ranked {len(repos)} repos -> top {len(result)}: {[r.get('full_name') for r in result]}")
        return result

    def score_github_issue(self, issue: Dict[str, Any], keyword: str) -> float:
        """
        Score a single GitHub issue (Search Issues API shape) 0-100.

        Returns -1.0 for hard-excluded issues (tutorial/intern/practice
        content) - deliberately NOT 0.0 like score_github_repo(), because
        an issue with zero reactions/comments and no keyword bonus is
        still a real, potentially relevant result (GitHub's own Search
        Issues relevance ordering already did the primary filtering -
        see github_fetcher.py's module docstring). 0.0 here means "no
        bonus signal", not "reject" - only an EXCLUDE_TERMS match is
        ever dropped by rank_github_issues().
        """
        repo = (issue.get("repository_url") or "").rsplit("/repos/", 1)[-1]
        title = (issue.get("title") or "").lower()
        body = (issue.get("body") or "").lower()
        searchable = f"{repo.lower()} {title} {body}"

        if self._is_excluded_text(searchable):
            return -1.0

        score = 0.0

        # Reactions: reader engagement signal (0-30 pts) - a scaled-down
        # analog of score_github_repo's star thresholds, since a single
        # issue rarely accumulates repo-scale reaction counts.
        reactions = issue.get("reactions") or {}
        engagement = int(reactions.get("+1") or 0) + int(reactions.get("heart") or 0)
        if engagement >= 20:
            score += 30
        elif engagement >= 5:
            score += 20
        elif engagement >= 1:
            score += 10

        # Comments: other users chiming in on the same problem (0-30
        # pts) - the issue-level analog of score_github_repo's
        # open_issues_count ("has complaints") signal. The Search Issues
        # API returns this as a top-level count, no extra call needed.
        comments = int(issue.get("comments") or 0)
        if comments >= 20:
            score += 30
        elif comments >= 5:
            score += 20
        elif comments >= 1:
            score += 10

        # Keyword match in title/body (0-40 pts) - same >3-char
        # substring logic as score_github_repo, weighted higher here
        # since it's one of only two positive signals available (no
        # forks equivalent for a single issue).
        words = [w for w in keyword.lower().split() if len(w) > 3]
        matches = sum(1 for w in words if w in searchable)
        score += min(matches * 20, 40)

        return min(score, 100.0)

    def rank_github_issues(self, issues: List[Dict[str, Any]], keyword: str, top_n: int) -> List[Dict[str, Any]]:
        """
        Score, hard-exclude, and rank issues. Returns up to top_n issues,
        highest-relevance first.

        Unlike rank_github_repos(), does NOT drop or fall back on issues
        that merely scored 0.0 (see score_github_issue()'s own
        docstring) - only EXCLUDE_TERMS matches (score -1.0) are ever
        removed. Returns an empty list (not a fallback) if every issue
        found was excluded - github_fetcher.py turns that into a loud,
        specific FetcherError rather than silently returning junk.
        """
        scored = [(issue, self.score_github_issue(issue, keyword)) for issue in issues]
        valid = [(i, s) for i, s in scored if s >= 0]

        if not valid:
            logger.warning(f"All {len(issues)} issue(s) excluded as tutorial/practice/intern content.")
            return []

        valid.sort(key=lambda x: x[1], reverse=True)

        result = [i for i, s in valid[:top_n]]
        logger.info(f"Ranked {len(issues)} issue(s) -> kept {len(result)} of {len(valid)} non-excluded")
        return result
