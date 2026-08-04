"""API routes - the only place in src/api/ that touches pipeline
internals, and even here, only through src.pipeline.pipeline's public
Pipeline/PipelineConfig contract, plus src.config.load_config (a plain
dataclass loader with no provider/fetcher/report logic of its own).

Independence rule (Task 10 requirement 9): this module never imports
src.ai.*, src.fetchers.*, or src.reporting.report_generator / formatter
- every fetch, extraction, clustering, verification, and report-
rendering decision happens inside Pipeline.run() exactly as it already
does for the CLI (src/pipeline/runner.py). The only imports from
src.reporting are the plain dataclasses in src.reporting.models
(InsightReport, OpportunityReportEntry, ProjectHealthSummary) - pure
data shapes with no rendering or generation logic in them, used here
solely as type hints while converting Pipeline's already-computed
output into JSON-serializable Pydantic models. Nothing here recomputes
a score, a cluster, a verification status, or a recommendation.

Report persistence and ID correlation:
Pipeline.run() always writes output_dir/pipeline_run_<id>.json (the
execution summary), unconditionally, even on failure - and additionally
output_dir/report_<id>.md when report_format includes markdown and a
report was actually produced. Both filenames share the same <id>,
chosen internally by pipeline.py (start_time formatted as
%Y%m%d_%H%M%S). This module treats <id> as an opaque token read back
off real files on disk, never a value it invents: after a run, it
locates the just-written summary file by matching its saved start_time
field against the run's own result.summary.start_time, rather than
reproducing pipeline.py's timestamp format string itself - so a future
change to that internal format can't silently break ID correlation
here (see _find_report_id_for).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import ValidationError

from src.api.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    ExecutionSummaryModel,
    HealthResponse,
    InsightReportModel,
    OpportunityEntryModel,
    ProjectHealthModel,
    ReportDetail,
    ReportListItem,
    Source,
    VersionResponse,
)
from src.config import load_config
from src.pipeline.pipeline import Pipeline, PipelineConfig, PipelineExecutionSummary
from src.reporting.models import InsightReport

logger = logging.getLogger(__name__)

router = APIRouter()

API_VERSION = "1.0.0"

# Matches src/pipeline/runner.py's own default output directory, so CLI
# runs and API runs are listed together in GET /reports - one output
# history, not two disconnected ones.
_OUTPUT_DIR = Path("output")
_SUMMARY_GLOB = "pipeline_run_*.json"
_SUMMARY_PREFIX = "pipeline_run_"
_REPORT_PREFIX = "report_"


# --- Health / version ----------------------------------------------------------------


@router.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    """Liveness + configuration presence only - deliberately does not
    contact Gemini or Reddit (that's what `python -m src.check_connections`
    is for). A health check that spent real API quota on every probe
    would be its own bug.
    """
    config = load_config()
    return HealthResponse(
        status="ok",
        gemini_configured=config.gemini_configured,
        reddit_configured=config.reddit_configured,
    )


@router.get("/version", response_model=VersionResponse, tags=["meta"])
def version() -> VersionResponse:
    return VersionResponse(name="MarketRadar API", version=API_VERSION, pipeline_module="src.pipeline.pipeline")


# --- Analyze --------------------------------------------------------------------------


@router.post("/analyze", response_model=AnalyzeResponse, tags=["analyze"])
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Runs the real pipeline: real Reddit/Gemini if configured in
    .env, mock fallback otherwise - identical "auto" semantics to
    `python -m src.pipeline.runner`. May consume real API quota and
    take several seconds to minutes depending on `limit`; see
    POST /analyze/mock for an always-free, always-offline equivalent.

    Returns HTTP 200 with a structured body even when the underlying
    run reports failure (summary.succeeded=false) - the pipeline ran
    and produced a valid, honest result, which is a successful API
    call by REST convention; the failure itself is data, not a
    transport-level error. See the architecture review in SESSION.md
    for the reasoning against mapping pipeline failure to a 5xx here.
    """
    return _run_and_build_response(request, force_mock=False)


@router.post("/analyze/mock", response_model=AnalyzeResponse, tags=["analyze"])
def analyze_mock(request: AnalyzeRequest) -> AnalyzeResponse:
    """Identical to POST /analyze except both fetching and analysis are
    forced to mock mode, regardless of .env - zero network calls, zero
    cost. Equivalent to `python -m src.pipeline.runner --mock`.
    """
    return _run_and_build_response(request, force_mock=True)


_SSE_KEEPALIVE_SECONDS = 15.0


@router.get("/analyze/stream", tags=["analyze"])
async def analyze_stream(
    keyword: Optional[str] = Query(default=None),
    source: Source = Query(default="reddit"),
    limit: int = Query(default=25, ge=1, le=100),
    use_cache: bool = Query(default=True),
    subreddit: str = Query(default="all"),
) -> StreamingResponse:
    """Server-Sent Events variant of POST /analyze: streams
    Pipeline.run()'s on_progress callback live (see
    src/pipeline/pipeline.py) instead of blocking silently for the
    whole run and returning one JSON body at the end.

    GET with query parameters, not POST with a JSON body like
    POST /analyze - a real technical constraint, not a style choice:
    the browser's native EventSource API (the standard SSE consumer)
    only supports GET requests with no custom body.

    Accepts the same validation AnalyzeRequest already enforces
    (blank subreddit rejected, keyword required for source="github",
    limit capped at 100) by constructing one internally from these
    query parameters rather than duplicating those rules here.

    Only progress events are streamed - the final AnalyzeResponse
    (report_id, the full InsightReport) is NOT sent over this stream.
    A consumer that needs those still has to call POST /analyze or
    GET /reports/{report_id} separately once the stream ends. Named
    limitation, not fixed here - out of this task's scope.

    "auto" semantics only (real if configured, mock fallback
    otherwise), matching POST /analyze - no /analyze/stream/mock
    variant exists, since one wasn't requested.
    """
    try:
        request = AnalyzeRequest(keyword=keyword, source=source, limit=limit, use_cache=use_cache, subreddit=subreddit)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    config = PipelineConfig(
        subreddit=request.subreddit,
        keyword=request.keyword,
        post_limit=request.limit,
        output_dir=_OUTPUT_DIR,
        ai_provider="auto",
        report_format=request.report_format,
        force_mock_fetch=False,
        cache_enabled=request.use_cache,
        source=request.source,
    )

    async def event_generator():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def on_progress(stage: str, message: str, percent: int) -> None:
            # Called from the executor thread running Pipeline.run()
            # below, never from this coroutine's own thread -
            # asyncio.Queue is documented as not thread-safe, so this
            # handoff must go through call_soon_threadsafe rather than
            # a direct queue.put_nowait() from that other thread.
            loop.call_soon_threadsafe(queue.put_nowait, {"stage": stage, "message": message, "percent": percent})

        async def run_pipeline() -> None:
            try:
                await loop.run_in_executor(None, lambda: Pipeline(config).run(on_progress=on_progress))
            finally:
                # Always signal the end of the stream, even if
                # something above raised unexpectedly - Pipeline.run()
                # itself is documented to never raise, but this
                # guarantees the generator below still terminates
                # instead of hanging open indefinitely.
                loop.call_soon_threadsafe(queue.put_nowait, None)

        task = asyncio.create_task(run_pipeline())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_SSE_KEEPALIVE_SECONDS)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            # Best-effort only if the client disconnects early: Python
            # cannot forcibly interrupt a thread already running inside
            # run_in_executor, so a cancelled task's underlying
            # Pipeline.run() call keeps running to completion in the
            # background regardless - this only stops this generator's
            # own bookkeeping, not the real work. Named limitation.
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _run_and_build_response(request: AnalyzeRequest, *, force_mock: bool) -> AnalyzeResponse:
    config = PipelineConfig(
        subreddit=request.subreddit,
        keyword=request.keyword,
        post_limit=request.limit,
        num_reports=request.num_reports,
        output_dir=_OUTPUT_DIR,
        ai_provider="mock" if force_mock else "auto",
        report_format=request.report_format,
        force_mock_fetch=force_mock,
        cache_enabled=request.use_cache,
        source=request.source,
    )
    result = Pipeline(config).run()
    report_id = _find_report_id_for(result.summary.start_time)
    return AnalyzeResponse(
        report_id=report_id,
        summary=_summary_to_model(result.summary),
        report=_report_to_model(result.report) if result.report is not None else None,
    )


# --- Reports ---------------------------------------------------------------------------


@router.get("/reports", response_model=List[ReportListItem], tags=["reports"])
def list_reports(limit: int = Query(default=20, ge=1, le=100)) -> List[ReportListItem]:
    """Lists past runs (CLI and API alike), newest first, read directly
    from the execution-summary JSON files Pipeline.run() already saves
    - no separate index/database is maintained.
    """
    items: List[ReportListItem] = []
    for path in _list_summary_files():
        try:
            data = _read_summary_file(path)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping unreadable report summary %s (%s)", path, type(exc).__name__)
            continue
        report_id = _report_id_from_summary_path(path)
        items.append(
            ReportListItem(
                report_id=report_id,
                start_time=data["start_time"],
                succeeded=data["succeeded"],
                posts_fetched=data["posts_fetched"],
                posts_analyzed=data["posts_analyzed"],
                clusters_found=data["clusters_found"],
                has_markdown_report=_markdown_path(report_id).exists(),
            )
        )
        if len(items) >= limit:
            break
    return items


@router.get("/reports/{report_id}", response_model=ReportDetail, tags=["reports"])
def get_report(report_id: str) -> ReportDetail:
    summary_path = _summary_path(report_id)
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail=f"No report found with id {report_id!r}.")

    try:
        data = _read_summary_file(summary_path)
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=500, detail=f"Report {report_id!r} exists but could not be read ({type(exc).__name__})."
        ) from exc

    markdown_path = _markdown_path(report_id)
    markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else None

    return ReportDetail(report_id=report_id, summary=ExecutionSummaryModel(**data), markdown=markdown)


@router.get("/download/{report_id}", tags=["reports"])
def download_report(report_id: str) -> FileResponse:
    markdown_path = _markdown_path(report_id)
    if not markdown_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"No Markdown report file for id {report_id!r} - either this report_id does not exist, or the "
                f"run that produced it used report_format='terminal' (no file was ever saved)."
            ),
        )
    return FileResponse(markdown_path, media_type="text/markdown", filename=markdown_path.name)


# --- Conversion helpers (dataclass -> Pydantic; no business logic) ---------------------


def _summary_to_model(summary: PipelineExecutionSummary) -> ExecutionSummaryModel:
    return ExecutionSummaryModel(
        start_time=summary.start_time,
        end_time=summary.end_time,
        duration_seconds=summary.duration_seconds,
        posts_fetched=summary.posts_fetched,
        posts_analyzed=summary.posts_analyzed,
        ai_calls_made=summary.ai_calls_made,
        cache_hits=summary.cache_hits,
        cache_misses=summary.cache_misses,
        clusters_found=summary.clusters_found,
        errors=summary.errors,
        report_path=str(summary.report_path) if summary.report_path else None,
        succeeded=summary.succeeded,
    )


def _report_to_model(report: InsightReport) -> InsightReportModel:
    return InsightReportModel(
        executive_summary=report.executive_summary,
        top_opportunities=[
            OpportunityEntryModel(
                title=entry.title,
                opportunity_score=entry.opportunity_score,
                confidence=entry.confidence,
                frequency=entry.frequency,
                verification_rate=entry.verification_rate,
                has_verification_data=entry.has_verification_data,
                supporting_quotes=entry.supporting_quotes,
                representative_discussions=entry.representative_discussions,
                suggested_customer_segment=entry.suggested_customer_segment,
                recommended_next_action=entry.recommended_next_action,
            )
            for entry in report.top_opportunities
        ],
        project_health=ProjectHealthModel(
            total_discussions_fetched=report.project_health.total_discussions_fetched,
            total_discussions_analyzed=report.project_health.total_discussions_analyzed,
            total_opportunity_clusters=report.project_health.total_opportunity_clusters,
            total_verified_insights=report.project_health.total_verified_insights,
            verification_percentage=report.project_health.verification_percentage,
            ai_provider_used=report.project_health.ai_provider_used,
            analysis_timestamp=report.project_health.analysis_timestamp,
        ),
    )


# --- Report-file lookup helpers ---------------------------------------------------------


def _list_summary_files() -> List[Path]:
    if not _OUTPUT_DIR.exists():
        return []
    return sorted(_OUTPUT_DIR.glob(_SUMMARY_GLOB), key=lambda p: p.stat().st_mtime, reverse=True)


def _report_id_from_summary_path(path: Path) -> str:
    return path.stem[len(_SUMMARY_PREFIX):]


def _summary_path(report_id: str) -> Path:
    return _OUTPUT_DIR / f"{_SUMMARY_PREFIX}{report_id}.json"


def _markdown_path(report_id: str) -> Path:
    return _OUTPUT_DIR / f"{_REPORT_PREFIX}{report_id}.md"


def _read_summary_file(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_report_id_for(start_time: datetime) -> Optional[str]:
    """Locates the summary file a just-completed run wrote, by matching
    its saved start_time back to the run's own result - a content
    match, not a filename-format guess (see module docstring).
    Pipeline.run() always writes this file, even on failure, so a miss
    here indicates a real bug in this correlation step itself, not an
    expected outcome - logged loudly rather than silently swallowed,
    and surfaced to the caller as report_id=None rather than raised,
    since the analysis result itself is still valid and worth returning.
    """
    target = start_time.isoformat()
    for path in _list_summary_files():
        try:
            data = _read_summary_file(path)
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("start_time") == target:
            return _report_id_from_summary_path(path)
    logger.error("Could not correlate a report_id for run started at %s - summary file missing or unreadable.", target)
    return None
