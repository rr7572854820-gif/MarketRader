"""Task 3 demo: Fetch -> Analyze -> Print formatted business insights.

Run from the project root:
    python -m src.analyze_preview COMMUNITY [--keyword X] [--limit N]

Uses the same Fetcher (src/fetchers/) and AIProvider (src/ai/)
abstractions as the rest of the project — works identically against
mock or real Reddit data, and against Gemini or any future AI provider,
with no changes to this file.

Every opportunity_score, urgency_score, user_persona, and
startup_opportunity printed here is explicitly labeled SPECULATIVE in
the output — see src/insights/models.py for why that label is not
optional.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from src.ai import get_ai_provider
from src.config import load_config
from src.fetchers import FetcherError, get_fetcher
from src.insights.aggregator import Aggregator
from src.insights.extractor import Extractor, InsightExtractionError
from src.insights.models import DiscussionInsight, OpportunityCluster
from src.models import FetchQuery


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch, analyze, and print business insights (Task 3 demo)."
    )
    parser.add_argument(
        "community", help="Subreddit name. Ignored in mock mode, but still required."
    )
    parser.add_argument("--keyword", default=None, help="Optional keyword filter.")
    parser.add_argument("--limit", type=int, default=25, help="Max posts to fetch.")
    return parser.parse_args(argv)


def _print_insight(index: int, insight: DiscussionInsight) -> None:
    mock_tag = " [MOCK SOURCE]" if insight.is_mock_source else ""
    print(f"--- Discussion #{index}{mock_tag} ---")
    print(f"Source: {insight.source_url}")
    print(f"Primary pain point: {insight.primary_pain_point.description}")
    print(f'  Evidence: "{insight.primary_pain_point.evidence_quote}"')
    if insight.secondary_pain_points:
        print("Secondary pain points:")
        for pp in insight.secondary_pain_points:
            print(f'  - {pp.description} ("{pp.evidence_quote}")')
    print(f"User persona [SPECULATIVE]: {insight.user_persona}")
    if insight.feature_requests:
        print(f"Feature requests: {', '.join(insight.feature_requests)}")
    if insight.buying_signals:
        print("Buying signals (verified quotes):")
        for quote in insight.buying_signals:
            print(f'  - "{quote}"')
    print(f"Emotional sentiment: {insight.emotional_sentiment.value}")
    print(f"Urgency [SPECULATIVE, 1-10]: {insight.urgency_score}")
    print(
        f"Opportunity score [SPECULATIVE, 1-100, single-source, NOT a verdict]: "
        f"{insight.opportunity_score}"
    )
    print(f"Confidence: {insight.confidence.value}")
    print(f"Startup opportunity [SPECULATIVE]: {insight.startup_opportunity}")
    if insight.supporting_evidence:
        print("Supporting evidence (verified quotes):")
        for quote in insight.supporting_evidence:
            print(f'  - "{quote}"')
    print()


def _print_cluster(index: int, cluster: OpportunityCluster) -> None:
    print(f"#{index} [{cluster.confidence.value} confidence] {cluster.label}")
    print(
        f"    Occurrences: {cluster.occurrence_count}  |  "
        f"Avg opportunity [SPECULATIVE]: {cluster.average_opportunity_score}  |  "
        f"Avg urgency [SPECULATIVE]: {cluster.average_urgency_score}"
    )
    for insight in cluster.insights:
        print(f"    - {insight.source_url}")
    print()


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    config = load_config()

    fetcher = get_fetcher(config)
    ai_provider = get_ai_provider(config)
    extractor = Extractor(ai_provider)

    fetch_mode = "REAL Reddit data" if config.reddit_configured else "MOCK sample data"
    ai_mode = "REAL Gemini" if config.gemini_configured else "MOCK AI provider"
    print(f"Fetching using: {fetch_mode}")
    print(f"Analyzing using: {ai_mode}\n")

    query = FetchQuery(community=args.community, keyword=args.keyword, limit=args.limit)

    try:
        posts = fetcher.fetch(query)
    except FetcherError as exc:
        print(f"[FAIL] Fetch failed: {exc}")
        return 1

    if not posts:
        print("No posts returned.")
        return 0

    insights: List[DiscussionInsight] = []
    for post in posts:
        try:
            insights.append(extractor.extract(post))
        except InsightExtractionError as exc:
            print(f"[SKIP] Could not analyze {post.url}: {exc}")

    if not insights:
        print("No discussions could be analyzed.")
        return 1

    print(f"\n=== {len(insights)} discussion(s) analyzed ===\n")
    for i, insight in enumerate(insights, start=1):
        _print_insight(i, insight)

    aggregator = Aggregator(ai_provider)
    clusters = aggregator.aggregate(insights)
    if aggregator.last_method == "lexical_fallback":
        print(
            f"[WARN] AI-assisted clustering unavailable "
            f"({aggregator.last_fallback_reason}); used keyword-overlap "
            f"clustering instead, which is known to under-merge real "
            f"duplicates — see SESSION.md.\n"
        )
    print(f"=== {len(clusters)} opportunity cluster(s), ranked (via {aggregator.last_method}) ===\n")
    for i, cluster in enumerate(clusters, start=1):
        _print_cluster(i, cluster)

    return 0


if __name__ == "__main__":
    sys.exit(main())
