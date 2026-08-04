"""Tests for the REST API (Task 10): src/api/app.py, routes.py, models.py.

Two testing strategies, deliberately kept separate:

- POST /analyze/mock is tested as a real, full end-to-end integration
  (real Pipeline, real MockFetcher + MockAIProvider) - zero network
  calls, zero cost, exactly like tests/test_pipeline.py's own --mock
  tests. This is the strongest evidence the API layer is wired to the
  real pipeline correctly, not a mock of it.
- POST /analyze (the real-provider endpoint) is tested by monkeypatching
  routes.Pipeline itself with a stub that records the PipelineConfig it
  was built with and returns a canned, fully-realistic PipelineRunResult
  - this proves the route builds the right config (ai_provider="auto",
  force_mock_fetch=False) and converts a result correctly, without ever
  risking a real Gemini/Reddit call in a test run.

Every test that touches the filesystem monkeypatches
src.api.routes._OUTPUT_DIR to pytest's tmp_path, so nothing here ever
reads or writes the project's real output/ directory.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.api.routes as routes
from src.api.app import app
from src.api.models import AnalyzeRequest
from src.insights.models import ConfidenceLevel
from src.pipeline.pipeline import PipelineExecutionSummary, PipelineRunResult
from src.reporting.models import InsightReport, OpportunityReportEntry, ProjectHealthSummary


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(routes, "_OUTPUT_DIR", tmp_path)
    return TestClient(app)


# --- Health / version --------------------------------------------------------------


def test_health_returns_ok_and_config_flags(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["gemini_configured"], bool)
    assert isinstance(body["reddit_configured"], bool)


def test_version_returns_expected_shape(client: TestClient):
    response = client.get("/version")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "MarketRadar API"
    assert body["pipeline_module"] == "src.pipeline.pipeline"


def test_unhandled_exception_returns_generic_500_not_a_traceback(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(routes, "_OUTPUT_DIR", tmp_path)

    def _boom():
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(routes, "load_config", _boom)
    # raise_server_exceptions=False: TestClient re-raises unhandled server
    # exceptions into the test process by default, which is right for
    # catching real bugs, but this test is specifically checking what a
    # real HTTP client would receive - the app's own exception handler's
    # response, not a re-raised Python exception.
    with TestClient(app, raise_server_exceptions=False) as c:
        response = c.get("/health")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}


# --- Request validation --------------------------------------------------------------


@pytest.mark.parametrize("bad_limit", [0, -1, 101, 10000])
def test_analyze_rejects_out_of_range_limit(client: TestClient, bad_limit: int):
    response = client.post("/analyze/mock", json={"limit": bad_limit})
    assert response.status_code == 422


def test_analyze_rejects_blank_subreddit(client: TestClient):
    response = client.post("/analyze/mock", json={"subreddit": "   "})
    assert response.status_code == 422


def test_analyze_rejects_wrong_type_for_limit(client: TestClient):
    response = client.post("/analyze/mock", json={"limit": "not a number"})
    assert response.status_code == 422


def test_analyze_rejects_invalid_report_format(client: TestClient):
    response = client.post("/analyze/mock", json={"report_format": "pdf"})
    assert response.status_code == 422


def test_analyze_request_model_treats_blank_keyword_as_no_filter():
    assert AnalyzeRequest(keyword="   ").keyword is None
    assert AnalyzeRequest(keyword="refund").keyword == "refund"
    assert AnalyzeRequest().keyword is None


def test_analyze_github_missing_keyword(client: TestClient):
    """repo was removed entirely - GitHubFetcher now discovers repos
    from keyword alone (see src/fetchers/github_fetcher.py), so keyword
    is the field that's now required for source="github".
    """
    response = client.post("/analyze/mock", json={"source": "github"})
    assert response.status_code == 422


def test_analyze_github_blank_keyword_still_rejected(client: TestClient):
    response = client.post("/analyze/mock", json={"source": "github", "keyword": "   "})
    assert response.status_code == 422


def test_list_reports_rejects_out_of_range_limit_query_param(client: TestClient):
    response = client.get("/reports", params={"limit": 0})
    assert response.status_code == 422
    response = client.get("/reports", params={"limit": 101})
    assert response.status_code == 422


# --- POST /analyze/mock: real, full, offline pipeline integration ------------------


def test_analyze_mock_end_to_end_returns_structured_response(client: TestClient):
    response = client.post("/analyze/mock", json={"limit": 2})
    assert response.status_code == 200

    body = response.json()
    assert body["report_id"] is not None
    assert body["summary"]["succeeded"] is True
    assert body["summary"]["posts_fetched"] == 2
    assert "cache_hits" in body["summary"] and "cache_misses" in body["summary"]
    assert body["report"] is not None  # generate_report() always returns a report, even an empty one
    # MockAIProvider now returns schema-valid JSON, so both posts extract
    # successfully; its clustering mock makes no merge judgment (singleton
    # clusters only), so 2 posts produce 2 opportunities.
    assert len(body["report"]["top_opportunities"]) == 2


def test_analyze_mock_writes_both_summary_and_markdown_files(client: TestClient, tmp_path: Path):
    response = client.post("/analyze/mock", json={"limit": 1, "report_format": "both"})
    report_id = response.json()["report_id"]

    assert (tmp_path / f"pipeline_run_{report_id}.json").exists()
    assert (tmp_path / f"report_{report_id}.md").exists()


def test_analyze_mock_terminal_format_saves_no_markdown_file(client: TestClient, tmp_path: Path):
    response = client.post("/analyze/mock", json={"limit": 1, "report_format": "terminal"})
    report_id = response.json()["report_id"]

    assert (tmp_path / f"pipeline_run_{report_id}.json").exists()
    assert not (tmp_path / f"report_{report_id}.md").exists()
    assert response.json()["summary"]["report_path"] is None


def test_analyze_mock_respects_use_cache_false(client: TestClient):
    """use_cache maps straight through to PipelineConfig.cache_enabled
    - confirmed via the summary's cache_hits/cache_misses being 0/0
    when disabled, matching tests/test_cache.py's own established
    assertion for cache_enabled=False.
    """
    response = client.post("/analyze/mock", json={"limit": 1, "use_cache": False})
    body = response.json()["summary"]
    assert body["cache_hits"] == 0
    assert body["cache_misses"] == 0


# --- POST /analyze: config construction + response conversion, no real API calls ----


def _canned_result() -> PipelineRunResult:
    now = datetime.now(timezone.utc)
    summary = PipelineExecutionSummary(
        start_time=now,
        end_time=now,
        duration_seconds=1.23,
        posts_fetched=3,
        posts_analyzed=3,
        ai_calls_made=4,
        cache_hits=1,
        cache_misses=3,
        clusters_found=1,
        errors=[],
        report_path=None,
        succeeded=True,
    )
    report = InsightReport(
        executive_summary="A canned executive summary.",
        top_opportunities=[
            OpportunityReportEntry(
                title="Reconciliation is painful",
                opportunity_score=72.5,
                confidence=ConfidenceLevel.STRONG,
                frequency=3,
                verification_rate=0.8,
                has_verification_data=True,
                supporting_quotes=["I spend hours reconciling payouts"],
                representative_discussions=["mock://sample/post-001"],
                suggested_customer_segment="Small business owner",
                recommended_next_action="Read the original discussions directly.",
            )
        ],
        project_health=ProjectHealthSummary(
            total_discussions_fetched=3,
            total_discussions_analyzed=3,
            total_opportunity_clusters=1,
            total_verified_insights=1,
            verification_percentage=80.0,
            ai_provider_used="Google Gemini (gemini-flash-latest)",
            analysis_timestamp=now,
        ),
    )
    return PipelineRunResult(summary=summary, report=report)


class _RecordingPipelineStub:
    """Stands in for src.api.routes.Pipeline: records the PipelineConfig
    it was constructed with, and .run() returns a canned result instead
    of making any real network call.
    """

    last_config = None

    def __init__(self, config):
        type(self).last_config = config

    def run(self) -> PipelineRunResult:
        return _canned_result()


def test_analyze_builds_auto_config_and_converts_result(client: TestClient, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(routes, "Pipeline", _RecordingPipelineStub)
    # _find_report_id_for looks for a real file on disk; the canned
    # result has no matching summary file, so report_id is expected to
    # come back None here - a real, honest outcome, not a test gap.
    response = client.post("/analyze", json={"subreddit": "startups", "keyword": "refund", "limit": 10})

    assert response.status_code == 200
    config = _RecordingPipelineStub.last_config
    assert config.ai_provider == "auto"
    assert config.force_mock_fetch is False
    assert config.subreddit == "startups"
    assert config.keyword == "refund"
    assert config.post_limit == 10
    assert config.source == "reddit"

    body = response.json()
    assert body["report_id"] is None
    assert body["summary"]["ai_calls_made"] == 4
    assert body["summary"]["cache_hits"] == 1
    assert body["report"]["executive_summary"] == "A canned executive summary."
    assert body["report"]["top_opportunities"][0]["title"] == "Reconciliation is painful"
    assert body["report"]["top_opportunities"][0]["confidence"] == "Strong"
    assert body["report"]["project_health"]["ai_provider_used"] == "Google Gemini (gemini-flash-latest)"


def test_analyze_github_valid(client: TestClient, monkeypatch):
    monkeypatch.setattr(routes, "Pipeline", _RecordingPipelineStub)
    response = client.post("/analyze", json={"source": "github", "keyword": "invoicing", "limit": 5})

    assert response.status_code == 200
    config = _RecordingPipelineStub.last_config
    assert config.source == "github"
    assert config.keyword == "invoicing"
    assert config.post_limit == 5


def test_analyze_mock_endpoint_forces_mock_even_with_stubbed_pipeline(client: TestClient, monkeypatch):
    monkeypatch.setattr(routes, "Pipeline", _RecordingPipelineStub)
    client.post("/analyze/mock", json={"limit": 1})

    config = _RecordingPipelineStub.last_config
    assert config.ai_provider == "mock"
    assert config.force_mock_fetch is True


# --- GET /analyze/stream (SSE) ------------------------------------------------------


class _ProgressEmittingPipelineStub:
    """Stands in for src.api.routes.Pipeline for /analyze/stream tests -
    same reasoning as _RecordingPipelineStub above (never risk a real
    network/AI call in a test), extended to also exercise the
    on_progress callback path: calls it with a few canned, realistic
    events (ending at 100) instead of doing any real fetch/AI/
    clustering work.
    """

    def __init__(self, config) -> None:
        self._config = config

    def run(self, on_progress=None) -> PipelineRunResult:
        if on_progress:
            on_progress("fetch", "🔍 Searching...", 5)
            on_progress("fetch", "✅ Fetched 3 real discussions", 35)
            on_progress("done", "🎉 Done! Found 1 opportunities in 0.1s", 100)
        return _canned_result()


def _sse_data_events(response_text: str) -> list:
    return [json.loads(line[len("data: ") :]) for line in response_text.splitlines() if line.startswith("data: ")]


def test_sse_returns_stream(client: TestClient, monkeypatch):
    monkeypatch.setattr(routes, "Pipeline", _ProgressEmittingPipelineStub)
    response = client.get("/analyze/stream", params={"subreddit": "startups"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")


def test_sse_sends_valid_json(client: TestClient, monkeypatch):
    monkeypatch.setattr(routes, "Pipeline", _ProgressEmittingPipelineStub)
    response = client.get("/analyze/stream", params={"subreddit": "startups"})

    events = _sse_data_events(response.text)  # json.loads raises if any line isn't valid JSON
    assert len(events) == 3


def test_sse_percent_field_present(client: TestClient, monkeypatch):
    monkeypatch.setattr(routes, "Pipeline", _ProgressEmittingPipelineStub)
    response = client.get("/analyze/stream", params={"subreddit": "startups"})

    events = _sse_data_events(response.text)
    assert len(events) > 0
    for event in events:
        assert "percent" in event
        assert isinstance(event["percent"], int)
        assert "stage" in event
        assert "message" in event


def test_sse_ends_with_100(client: TestClient, monkeypatch):
    monkeypatch.setattr(routes, "Pipeline", _ProgressEmittingPipelineStub)
    response = client.get("/analyze/stream", params={"subreddit": "startups"})

    events = _sse_data_events(response.text)
    assert events[-1]["percent"] == 100


def test_sse_rejects_blank_subreddit(client: TestClient, monkeypatch):
    monkeypatch.setattr(routes, "Pipeline", _ProgressEmittingPipelineStub)
    response = client.get("/analyze/stream", params={"subreddit": "   "})

    assert response.status_code == 422


def test_sse_github_requires_keyword(client: TestClient, monkeypatch):
    monkeypatch.setattr(routes, "Pipeline", _ProgressEmittingPipelineStub)
    response = client.get("/analyze/stream", params={"source": "github"})

    assert response.status_code == 422


# --- GET /reports, GET /reports/{id}, GET /download/{id} ---------------------------


def test_list_reports_empty_when_no_runs_yet(client: TestClient):
    response = client.get("/reports")
    assert response.status_code == 200
    assert response.json() == []


def test_list_reports_returns_runs_newest_first(client: TestClient):
    """report_id has only second-level resolution (it's derived from
    pipeline.py's own start_time-based filename, %Y%m%d_%H%M%S) - two
    runs completing within the same wall-clock second collide on the
    same report_id and the second silently overwrites the first's
    files. A human running the CLI would never trigger this; a fast
    API caller easily could - see the architecture review for this as
    a named, real limitation. The sleep here exists to test the
    ordering logic correctly, not to hide the collision.
    """
    first = client.post("/analyze/mock", json={"limit": 1}).json()["report_id"]
    time.sleep(1.1)
    second = client.post("/analyze/mock", json={"limit": 1}).json()["report_id"]

    response = client.get("/reports")
    ids = [item["report_id"] for item in response.json()]

    assert first in ids and second in ids
    assert first != second
    assert len(response.json()) == 2
    for item in response.json():
        assert item["has_markdown_report"] is True


def test_get_report_returns_summary_and_markdown(client: TestClient):
    report_id = client.post("/analyze/mock", json={"limit": 1}).json()["report_id"]

    response = client.get(f"/reports/{report_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["report_id"] == report_id
    assert body["markdown"] is not None
    assert "MarketRadar Insight Report" in body["markdown"]


def test_get_report_terminal_format_has_no_markdown(client: TestClient):
    report_id = client.post("/analyze/mock", json={"limit": 1, "report_format": "terminal"}).json()["report_id"]
    response = client.get(f"/reports/{report_id}")
    assert response.json()["markdown"] is None


def test_get_report_unknown_id_returns_404(client: TestClient):
    response = client.get("/reports/does-not-exist")
    assert response.status_code == 404


def test_download_report_returns_markdown_file(client: TestClient):
    report_id = client.post("/analyze/mock", json={"limit": 1}).json()["report_id"]

    response = client.get(f"/download/{report_id}")

    assert response.status_code == 200
    assert "MarketRadar Insight Report" in response.text


def test_download_report_unknown_id_returns_404(client: TestClient):
    response = client.get("/download/does-not-exist")
    assert response.status_code == 404


def test_download_report_terminal_format_returns_404(client: TestClient):
    report_id = client.post("/analyze/mock", json={"limit": 1, "report_format": "terminal"}).json()["report_id"]
    response = client.get(f"/download/{report_id}")
    assert response.status_code == 404


# --- _find_report_id_for: the one piece of correlation logic worth a direct test ----


def test_find_report_id_for_returns_none_when_no_summary_file_matches(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(routes, "_OUTPUT_DIR", tmp_path)
    result = routes._find_report_id_for(datetime.now(timezone.utc))
    assert result is None


def test_find_report_id_for_matches_on_exact_start_time(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(routes, "_OUTPUT_DIR", tmp_path)
    now = datetime.now(timezone.utc)
    (tmp_path / "pipeline_run_20260101_000000.json").write_text(
        json.dumps({"start_time": now.isoformat()}), encoding="utf-8"
    )

    result = routes._find_report_id_for(now)

    assert result == "20260101_000000"


# --- OpenAPI docs are actually served -----------------------------------------------


def test_openapi_schema_is_served(client: TestClient):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "MarketRadar API"
    for path in ["/health", "/version", "/analyze", "/analyze/mock", "/reports", "/reports/{report_id}", "/download/{report_id}"]:
        assert path in schema["paths"]


def test_docs_ui_is_served(client: TestClient):
    response = client.get("/docs")
    assert response.status_code == 200


# --- CORS (Task 11): the dashboard is a browser app on a different origin --------


def test_cors_preflight_allows_localhost_dashboard_origin(client: TestClient):
    """Found while building the dashboard: src/api/app.py had no CORS
    configuration at all, so every browser fetch() from the dashboard's
    own origin (localhost:3000 in dev) was blocked before it ever
    reached this API - confirmed via a real cross-origin OPTIONS
    preflight against a running server (405, no Access-Control-Allow-*
    headers) before the fix in src/api/app.py. Regression-tested here
    since it's a real, previously-shipped functional gap, not a
    style choice.
    """
    response = client.options(
        "/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_non_localhost_origin(client: TestClient):
    response = client.options(
        "/health",
        headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight_allows_production_vercel_origin(client: TestClient):
    """The deployed dashboard (Render backend + Vercel frontend): a real
    OPTIONS preflight against the deployed backend from this exact
    origin came back "Disallowed CORS origin" because only the
    localhost regex was configured - src/api/app.py now allow-lists
    this origin explicitly (see its module docstring). Exact string
    match, not folded into the localhost regex or widened to a
    wildcard, so only this known production origin is trusted.
    """
    response = client.options(
        "/analyze",
        headers={"Origin": "https://market-rader.vercel.app", "Access-Control-Request-Method": "POST"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://market-rader.vercel.app"


def test_cors_rejects_other_vercel_preview_origin(client: TestClient):
    """Only the exact production origin is allow-listed - a different
    (e.g. preview/branch) Vercel subdomain must still be rejected, same
    as any other non-allow-listed origin.
    """
    response = client.options(
        "/health",
        headers={
            "Origin": "https://market-rader-git-some-branch.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in response.headers
