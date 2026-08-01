"""Pydantic request/response schemas for the API.

Response field shapes mirror the pipeline's own dataclasses
(src.pipeline.pipeline.PipelineExecutionSummary and
src.reporting.models.InsightReport / OpportunityReportEntry /
ProjectHealthSummary) so a response is a faithful JSON view of exactly
what the pipeline already computed - nothing in this file recomputes a
score, a cluster, or a recommendation. See src/api/routes.py for the
conversion functions that build these from live pipeline output.

Request validation mirrors src/pipeline/runner.py's CLI validation
(reject blank subreddit, treat blank keyword as "no filter") so the API
and CLI behave the same way given the same input - plus one addition
that has no CLI equivalent: `limit` is capped at 100 here. The CLI is a
human typing a command they can see the consequences of; a network-
facing endpoint can be hit programmatically with no such safeguard, so
an explicit upper bound is a deliberate, API-specific safety rail
against an accidental huge Gemini bill or a very long blocking request,
not a restriction pipeline.py itself imposes.

`source` (added when GitHubFetcher was wired end-to-end): mirrors
PipelineConfig's own source field - see src/pipeline/pipeline.py.
`subreddit` keeps its "all"/non-blank default and validation unchanged
for source="reddit"; it's simply ignored when source="github", the same
way it was already ignored against mock data.

`repo` was removed (GitHubFetcher's own repo-discovery feature, see
src/fetchers/github_fetcher.py's module docstring): a GitHub request no
longer names an exact repository - `keyword` alone drives both GitHub's
Search API (to find repos) and the existing post-fetch filter, so it is
now required, not optional, when source="github".
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from src.insights.models import ConfidenceLevel

ReportFormat = Literal["terminal", "markdown", "both"]
Source = Literal["reddit", "github"]


class AnalyzeRequest(BaseModel):
    keyword: Optional[str] = Field(
        default=None, description="Only include posts/comments containing this keyword (case-insensitive). Blank/whitespace-only is treated as no filter for Reddit, same as the CLI - but required when source='github', where it also drives repo discovery."
    )
    subreddit: str = Field(default="all", min_length=1, description="Subreddit to fetch from, without 'r/'. Ignored when source='github' or against mock data, but still validated.")
    source: Source = Field(default="reddit", description="Which Fetcher to use - 'reddit' (default) or 'github'.")
    limit: int = Field(default=25, ge=1, le=100, description="Maximum posts to fetch. Capped at 100 for this API (see module docstring).")
    use_cache: bool = Field(default=True, description="Reuse cached AI responses for identical prompts. Same semantics as the CLI's --no-cache when set to false.")
    report_format: ReportFormat = Field(default="both", description="'terminal' returns the report in the response only; 'markdown' saves a file only; 'both' does both.")

    @field_validator("subreddit")
    @classmethod
    def _reject_blank_subreddit(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("subreddit must not be blank")
        return stripped

    @field_validator("keyword")
    @classmethod
    def _blank_keyword_means_no_filter(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def _require_keyword_for_github_source(self) -> "AnalyzeRequest":
        if self.source == "github" and not self.keyword:
            raise ValueError("keyword is required for GitHub source")
        return self


class OpportunityEntryModel(BaseModel):
    title: str
    opportunity_score: float = Field(description="SPECULATIVE - AI-inferred, not a verified finding.")
    confidence: ConfidenceLevel
    frequency: int
    verification_rate: float
    has_verification_data: bool
    supporting_quotes: List[str] = Field(description="Only quotes independently marked VERIFIED by the Verifier - never a raw, unverified AI-extracted quote.")
    representative_discussions: List[str]
    suggested_customer_segment: str = Field(description="SPECULATIVE - AI-inferred, not a verified finding.")
    recommended_next_action: str = Field(description="A research action only - never a build/invest verdict.")


class ProjectHealthModel(BaseModel):
    total_discussions_fetched: int
    total_discussions_analyzed: int
    total_opportunity_clusters: int
    total_verified_insights: int
    verification_percentage: float
    ai_provider_used: str
    analysis_timestamp: datetime


class InsightReportModel(BaseModel):
    executive_summary: str
    top_opportunities: List[OpportunityEntryModel]
    project_health: ProjectHealthModel


class ExecutionSummaryModel(BaseModel):
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    posts_fetched: int
    posts_analyzed: int
    ai_calls_made: int
    cache_hits: int
    cache_misses: int
    clusters_found: int
    errors: List[str]
    report_path: Optional[str]
    succeeded: bool


class AnalyzeResponse(BaseModel):
    report_id: Optional[str] = Field(
        default=None,
        description="Use with GET /reports/{report_id} and GET /download/{report_id}. Only None if the pipeline's own execution-summary file could not be located after the run - see architecture review; should not happen in practice.",
    )
    summary: ExecutionSummaryModel
    report: Optional[InsightReportModel] = Field(
        default=None, description="None only when the run failed before a report could be generated (e.g. fetch failed entirely) - check summary.succeeded and summary.errors."
    )


class ReportListItem(BaseModel):
    report_id: str
    start_time: datetime
    succeeded: bool
    posts_fetched: int
    posts_analyzed: int
    clusters_found: int
    has_markdown_report: bool = Field(description="False if this run used report_format='terminal' (no file saved) or produced no report.")


class ReportDetail(BaseModel):
    report_id: str
    summary: ExecutionSummaryModel
    markdown: Optional[str] = Field(
        default=None,
        description="Raw saved Markdown report text, if a file exists for this report_id. The pipeline does not persist a JSON form of the full structured report for past runs - only the execution summary (always) and the rendered Markdown (when report_format included it). See architecture review for why this API does not reconstruct one by parsing the Markdown back.",
    )


class HealthResponse(BaseModel):
    status: Literal["ok"]
    gemini_configured: bool
    reddit_configured: bool


class VersionResponse(BaseModel):
    name: str
    version: str
    pipeline_module: str


class ErrorResponse(BaseModel):
    detail: str
