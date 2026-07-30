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

_EPILOG = """\
examples:
  # Fully offline, zero cost, zero network calls - good for a first run
  # or for testing without touching your Gemini quota:
  python -m src.pipeline.runner --mock

  # Real Reddit + real Gemini, targeting a specific subreddit:
  python -m src.pipeline.runner --subreddit startups

  # Filter fetched posts by keyword, and only save Markdown (no terminal dump):
  python -m src.pipeline.runner --keyword invoicing --format markdown

  # See exactly what's happening, including third-party library logs:
  python -m src.pipeline.runner --mock --verbose

Configuration (GEMINI_API_KEY, REDDIT_CLIENT_ID, etc.) is read from a
.env file in the project root - copy .env.example to .env and fill it
in. Reddit is optional; without it, --mock and real-Reddit runs both
still work by falling back to mock sample data. Run
`python -m src.check_connections` to verify your setup before a real run."""


def _positive_int(raw: str) -> int:
    """argparse type= validator for --limit — must be a positive whole
    number. Raising ArgumentTypeError here gives a clean, one-line CLI
    error (argparse catches it and prints usage + the message) instead
    of a raw traceback or a confusing empty/negative-limit fetch later.
    """
    try:
        value = int(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(f"must be a whole number, got {raw!r}") from None
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be greater than 0, got {value}")
    return value


def _non_blank(raw: str) -> str:
    """argparse type= validator — rejects "" or whitespace-only values
    with a clear message instead of silently passing a blank subreddit
    name through to the Fetcher.
    """
    stripped = raw.strip()
    if not stripped:
        raise argparse.ArgumentTypeError("must not be blank")
    return stripped


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.pipeline.runner",
        description="Run the full MarketRadar pipeline: Fetch -> Analyze -> Cluster -> Verify -> Report.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--subreddit",
        type=_non_blank,
        default="all",
        help="Subreddit to fetch from (without 'r/'), e.g. 'startups'. Ignored when running "
        "against mock data, but still validated. Default: 'all'.",
    )
    parser.add_argument(
        "--keyword",
        default=None,
        help="Only include posts/comments containing this keyword (case-insensitive). "
        "Applied during fetching. Omit to fetch without filtering.",
    )
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=25,
        help="Maximum number of posts to fetch. Must be a positive whole number. Default: 25.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory to save the Markdown report and the pipeline run summary JSON into "
        "(created automatically if it doesn't exist). Default: 'output'.",
    )
    parser.add_argument(
        "--ai-provider",
        choices=["auto", "mock"],
        default="auto",
        help="'auto' (default) uses real Gemini if GEMINI_API_KEY is set in .env, and falls back "
        "to the mock provider otherwise. 'mock' always forces the mock provider, even if a real "
        "key is configured - useful for a free dry run.",
    )
    parser.add_argument(
        "--format",
        choices=["terminal", "markdown", "both"],
        default="both",
        help="Where the report is shown: 'terminal' prints only, 'markdown' saves only, "
        "'both' does both (default).",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run the entire pipeline fully offline: forces both mock Reddit data and the mock "
        "AI provider, regardless of what's configured in .env. Zero network calls, zero cost. "
        "Equivalent to forcing the fetch step to mock and passing --ai-provider mock together.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show DEBUG-level log output, including third-party libraries (e.g. the Gemini "
        "SDK's own HTTP request logging) - normally suppressed to keep output readable. "
        "Use this when something needs real debugging.",
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

    force=True (Task 7): basicConfig() silently does nothing if the
    root logger already has handlers configured, which would make a
    second call to this function within the same process (e.g. two
    Pipeline runs from one long-lived caller, or simply two tests in
    one pytest session) silently fail to apply — found by exactly that
    happening in tests/test_pipeline.py. force=True makes this function
    correctly idempotent instead of "only works the first time."
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    logging.getLogger("src").setLevel(logging.INFO if not verbose else logging.DEBUG)


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
