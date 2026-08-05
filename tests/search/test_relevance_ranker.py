"""Tests for src/search/relevance_ranker.py.

Tests 1-8 exercise score_github_repo()/rank_github_repos() exactly as
given (repo-shaped dicts: full_name, stargazers_count, open_issues_count,
forks_count, description, topics).

Tests 9-10 exercise GitHubFetcher's actual integration point instead -
_discover_issues()/rank_github_issues() (issue-shaped dicts) - since
GitHubFetcher never sees repo objects at all (see relevance_ranker.py's
and github_fetcher.py's module docstrings for why). Local helpers here
are deliberately self-contained rather than importing
tests/fetchers/test_github_fetcher.py's fixtures, matching this
project's existing convention of small, file-local test fixtures.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.config import Config
from src.fetchers.github_fetcher import GitHubFetcher
from src.search.relevance_ranker import RelevanceRanker


# --- score_github_repo() / rank_github_repos() (given spec, repo-shaped) ---------------


def _repo(
    full_name: str = "someorg/somerepo",
    stars: int = 500,
    open_issues: int = 20,
    forks: int = 50,
    description: str = "a normal open source project",
    topics: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "full_name": full_name,
        "stargazers_count": stars,
        "open_issues_count": open_issues,
        "forks_count": forks,
        "description": description,
        "topics": topics or [],
    }


def test_intern_repo_scores_zero():
    ranker = RelevanceRanker()
    repo = _repo(full_name="someone/intern-project", stars=500, open_issues=20)

    assert ranker.score_github_repo(repo, "invoicing") == 0.0


def test_low_star_repo_scores_zero():
    ranker = RelevanceRanker()
    repo = _repo(stars=2, open_issues=1)

    assert ranker.score_github_repo(repo, "invoicing") == 0.0


def test_no_issues_scores_zero():
    ranker = RelevanceRanker()
    repo = _repo(stars=500, open_issues=0)

    assert ranker.score_github_repo(repo, "invoicing") == 0.0


def test_real_repo_scores_high():
    ranker = RelevanceRanker()
    repo = _repo(
        full_name="invoiceninja/invoiceninja",
        stars=7000,
        open_issues=150,
        forks=2000,
        description="Free invoicing and billing saas",
        topics=["invoicing", "saas", "billing"],
    )

    assert ranker.score_github_repo(repo, "invoicing") > 50


def test_keyword_match_boosts_score():
    ranker = RelevanceRanker()
    repo_a = _repo(full_name="someorg/invoicing-tool", stars=500, open_issues=20, forks=50, description="")
    repo_b = _repo(full_name="someorg/unrelated-tool", stars=500, open_issues=20, forks=50, description="")

    assert ranker.score_github_repo(repo_a, "invoicing") > ranker.score_github_repo(repo_b, "invoicing")


def test_rank_returns_top_n():
    ranker = RelevanceRanker()
    repos = [_repo(full_name=f"org/repo{i}", stars=100 + i, open_issues=10, forks=10) for i in range(10)]

    result = ranker.rank_github_repos(repos, "invoicing", top_n=5)

    assert len(result) == 5


def test_rank_excludes_zero_scored():
    ranker = RelevanceRanker()
    real_repos = [_repo(full_name=f"org/real{i}", stars=500, open_issues=20, forks=50) for i in range(3)]
    intern_repos = [
        _repo(full_name="someone/intern-project", stars=500, open_issues=20),
        _repo(full_name="student/homework-repo", stars=500, open_issues=20),
    ]

    result = ranker.rank_github_repos(real_repos + intern_repos, "invoicing", top_n=5)

    assert len(result) == 3
    assert all("intern" not in r["full_name"] and "homework" not in r["full_name"] for r in result)


def test_rank_fallback_all_zero():
    ranker = RelevanceRanker()
    repos = [_repo(full_name=f"org/repo{i}", stars=1, open_issues=1) for i in range(5)]  # all < 5 stars

    result = ranker.rank_github_repos(repos, "invoicing", top_n=5)  # must not raise

    assert len(result) <= 3


# --- GitHubFetcher integration (issue-shaped, the real wiring) -------------------------


def _config(token: Optional[str] = None) -> Config:
    return Config(
        gemini_api_key=None,
        gemini_model="gemini-flash-latest",
        reddit_client_id=None,
        reddit_client_secret=None,
        reddit_user_agent="test-agent",
        github_token=token,
    )


def _issue_dict(
    number: int,
    repo: str = "owner/repo",
    title: str = "",
    body: str = "",
    plus_one: int = 0,
    heart: int = 0,
    comments: int = 0,
) -> Dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "body": body,
        "repository_url": f"https://api.github.com/repos/{repo}",
        "reactions": {"+1": plus_one, "heart": heart},
        "comments": comments,
    }


def test_multi_term_search_deduplicates(monkeypatch):
    """The same issue turning up under two different search terms must
    only appear once in the final result - _discover_issues merges by
    "owner/repo#number" before ranking.
    """
    fetcher = GitHubFetcher(_config())
    same_issue = _issue_dict(number=1, repo="owner/repo", title="invoicing bug", body="invoicing is broken")

    monkeypatch.setattr(fetcher, "_search_issues", lambda keyword, limit: [same_issue])

    results = fetcher._discover_issues(["invoicing", "billing"], "invoicing", limit=10)

    assert len(results) == 1


def test_github_fetcher_uses_ranker(monkeypatch):
    """fetch() must exclude tutorial/intern/practice issues via the
    ranker while still returning genuinely relevant ones.
    """
    fetcher = GitHubFetcher(_config())

    real_issue = _issue_dict(
        number=1, repo="invoiceninja/invoiceninja", title="invoicing bug", body="invoicing breaks for large accounts"
    )
    intern_issue = _issue_dict(
        number=2, repo="someone/intern-project", title="my internship homework task", body="learning invoicing basics"
    )

    monkeypatch.setattr(fetcher, "_search_issues", lambda keyword, limit: [real_issue, intern_issue])
    monkeypatch.setattr(fetcher, "_issue_to_post", lambda issue: issue.get("title"))

    from src.models import FetchQuery

    results = fetcher.fetch(FetchQuery(community="ignored", keyword="invoicing", limit=10))

    assert "invoicing bug" in results
    assert "my internship homework task" not in results
