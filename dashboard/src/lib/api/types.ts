/**
 * TypeScript mirrors of the FastAPI backend's Pydantic response/request
 * schemas (see ../../../src/api/models.py in the Python project). These
 * are data shapes only, copied field-for-field from what the backend
 * already serializes as JSON - nothing here recomputes a score, a
 * cluster, a verification status, or a recommendation. The dashboard's
 * "no duplicated backend logic" rule is about business logic; typing
 * the wire format the backend already commits to is unavoidable for a
 * typed client, the same reasoning src/api/models.py itself used to
 * justify importing the plain dataclasses in src/reporting/models.py.
 *
 * Keep these in sync with src/api/models.py by hand - there is no
 * shared schema generation between the Python and TypeScript sides
 * (see the architecture review in SESSION.md's Task 11 entry for why
 * that's a named, deliberate simplicity tradeoff, not an oversight).
 */

export type ConfidenceLevel = "Strong" | "Moderate" | "Weak";

export type ReportFormat = "terminal" | "markdown" | "both";

export type Source = "reddit" | "github" | "hackernews" | "hn" | "all";

export interface AnalyzeRequest {
  keyword?: string | null;
  subreddit?: string;
  source?: Source;
  limit: number;
  use_cache: boolean;
  report_format: ReportFormat;
}

export interface OpportunityEntry {
  title: string;
  opportunity_score: number;
  confidence: ConfidenceLevel;
  frequency: number;
  verification_rate: number;
  has_verification_data: boolean;
  supporting_quotes: string[];
  representative_discussions: string[];
  suggested_customer_segment: string;
  recommended_next_action: string;
}

export interface ProjectHealth {
  total_discussions_fetched: number;
  total_discussions_analyzed: number;
  total_opportunity_clusters: number;
  total_verified_insights: number;
  verification_percentage: number;
  ai_provider_used: string;
  analysis_timestamp: string;
}

export interface InsightReport {
  executive_summary: string;
  top_opportunities: OpportunityEntry[];
  project_health: ProjectHealth;
}

export interface ExecutionSummary {
  start_time: string;
  end_time: string;
  duration_seconds: number;
  posts_fetched: number;
  posts_analyzed: number;
  ai_calls_made: number;
  cache_hits: number;
  cache_misses: number;
  clusters_found: number;
  errors: string[];
  report_path: string | null;
  succeeded: boolean;
}

export interface AnalyzeResponse {
  report_id: string | null;
  summary: ExecutionSummary;
  report: InsightReport | null;
}

export interface ReportListItem {
  report_id: string;
  start_time: string;
  succeeded: boolean;
  posts_fetched: number;
  posts_analyzed: number;
  clusters_found: number;
  has_markdown_report: boolean;
}

export interface ReportDetail {
  report_id: string;
  summary: ExecutionSummary;
  markdown: string | null;
}

export interface HealthResponse {
  status: "ok";
  gemini_configured: boolean;
  reddit_configured: boolean;
}

export interface VersionResponse {
  name: string;
  version: string;
  pipeline_module: string;
}
