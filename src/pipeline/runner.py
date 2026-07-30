"""CLI for running the full MarketRadar pipeline with a single command.

Examples:
    python -m src.pipeline.runner --subreddit startups
    python -m src.pipeline.runner --keyword invoicing
    python -m src.pipeline.runner --mock

--mock runs the entire pipeline fully offline: mock Reddit data AND
the mock AI provider, zero network calls, zero cost. Useful given how
easily the real Gemini free-tier daily quota gets exhausted during
active development (see SESSION.md).

This file owns all console output for the pipeline: configures Python
logging so Pipeline's operational log lines are visible, then prints
the terminal report (if requested) and a final human-readable run
summary based on what Pipeline.run() returns. Pipeline itself never
prints — see pipeline.py's module docstring for why.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from src.pipeline.pipeline import Pipeline, PipelineConfig, PipelineRunResult
from src.reporting.formatter import format_terminal


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full MarketRadar pipeline: Fetch -> Analyze -> Cluster -> Verify -> Report."
    )
    parser.add_argument(
        "--subreddit", default="all", help="Subreddit to fetch from. Ignored in mock mode. Default: 'all'."
    )
    parser.add_argument("--keyword", default=None, help="Optional keyword filter.")
    parser.add_argument("--limit", type=int, default=25, help="Max posts to fetch. Default: 25.")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output"), help="Where to save the report and run summary."
    )
    parser.add_argument(
        "--ai-provider",
        choices=["auto", "mock"],
        default="auto",
        help="'auto' uses real Gemini if GEMINI_API_KEY is set, mock otherwise (default). "
        "'mock' forces the mock provider regardless of configuration.",
    )
    parser.add_argument(
        "--format",
        choices=["terminal", "markdown", "both"],
        default="both",
        help="Report output format(s). Default: both.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run fully offline: forces both mock Reddit data and the mock AI provider "
        "(equivalent to forcing fetch to mock and --ai-provider mock together).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show DEBUG-level log output instead of INFO."
    )
    return parser.parse_args(argv)


def _configure_logging(verbose: bool) -> None:
    """Configures logging so only this project's own log lines show at
    INFO by default — third-party libraries (google-genai's HTTP/AFC
    logging, in particular) log at INFO too, and basicConfig's level
    applies to the root logger, which every library inherits from.
    Found by actually running this against real Gemini and seeing
    "AFC is enabled..." / raw HTTP request lines pollute the output.

    --verbose sets the root logger itself to DEBUG, so third-party
    libraries become visible too, for real debugging.
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    if not verbose:
        logging.getLogger("src").setLevel(logging.INFO)


def _print_run_summary(result: PipelineRunResult) -> None:
    summary = result.summary
    print("\n" + "=" * 70)
    print("PIPELINE EXECUTION SUMMARY")
    print("=" * 70)
    print(f"Start time:        {summary.start_time.isoformat()}")
    print(f"End time:          {summary.end_time.isoformat()}")
    print(f"Duration:          {summary.duration_seconds:.1f}s")
    print(f"Posts fetched:     {summary.posts_fetched}")
    print(f"Posts analyzed:    {summary.posts_analyzed}")
    print(f"AI calls made:     {summary.ai_calls_made}")
    print(f"Clusters found:    {summary.clusters_found}")
    print(f"Report location:   {summary.report_path if summary.report_path else '(not saved)'}")
    print(f"Succeeded:         {summary.succeeded}")
    if summary.errors:
        print(f"\nErrors/warnings ({len(summary.errors)}):")
        for error in summary.errors:
            print(f"  - {error}")
    print("=" * 70)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    _configure_logging(args.verbose)

    config = PipelineConfig(
        subreddit=args.subreddit,
        keyword=args.keyword,
        post_limit=args.limit,
        output_dir=args.output_dir,
        ai_provider="mock" if args.mock else args.ai_provider,
        report_format=args.format,
        force_mock_fetch=args.mock,
    )

    result = Pipeline(config).run()

    if config.report_format in ("terminal", "both") and result.report is not None:
        print(format_terminal(result.report))

    _print_run_summary(result)

    return 0 if result.summary.succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
