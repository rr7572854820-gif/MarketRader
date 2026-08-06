/**
 * The ONLY module in this dashboard that calls fetch() against the
 * MarketRadar backend. Every page and component goes through the
 * typed functions below - never a raw fetch() to the API elsewhere in
 * the codebase. This is the frontend's equivalent of the backend's own
 * "only communicate through Pipeline.run()" rule: one seam, one place
 * that knows the base URL, the error shape, and the endpoint paths.
 *
 * This client calls the REST API exactly as documented in README.md's
 * "REST API" section and src/api/routes.py - it never re-implements
 * fetching, analysis, clustering, verification, or report generation;
 * it only sends HTTP requests and parses HTTP responses.
 */

import { getApiBaseUrl } from "@/lib/settings";
import { ApiError, formatErrorDetail } from "@/lib/api/errors";
import type {
  AnalyzeRequest,
  AnalyzeResponse,
  HealthResponse,
  ReportDetail,
  ReportListItem,
  Source,
  VersionResponse,
} from "@/lib/api/types";

/** Query params GET /analyze/stream accepts - a curated subset of
 * AnalyzeRequest's fields (no report_format - the stream never returns
 * a report body, see analyze_stream's own docstring), matching exactly
 * what the backend endpoint itself takes as query parameters (see
 * src/api/routes.py::analyze_stream). subreddit is included even
 * though it wasn't in this feature's original prop list - source="reddit"
 * needs it to target the right subreddit; dropping it would silently
 * ignore the user's actual choice. num_reports was added alongside
 * source="all" oversampling - without it, source="all" (which always
 * streams, never goes through api.analyze()'s POST /analyze path -
 * see analysis-form.tsx's hasNoMockEquivalent()) had no way to trigger
 * Pipeline.run()'s num_reports-driven oversample/split-across-sources
 * behavior at all.
 */
export interface AnalyzeStreamParams {
  keyword?: string | null;
  source?: Source;
  limit: number;
  use_cache: boolean;
  subreddit?: string;
  num_reports?: number;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const baseUrl = getApiBaseUrl();
  let response: Response;

  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    // fetch() throws (not a rejected-with-status response) for network
    // failures: server not running, wrong host/port, CORS rejection,
    // offline. This is the "backend unreachable" case every page needs
    // to render distinctly from "backend returned an error".
    throw new ApiError(
      `Could not reach the MarketRadar API at ${baseUrl}. Is the server running (uvicorn src.api.app:app)? ` +
        `Check the API base URL in Settings if it's running somewhere else.`,
      null
    );
  }

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      // Response wasn't JSON (e.g. a proxy error page) - fall through
      // to the generic status-text message below.
    }
    const detail = formatErrorDetail(body);
    throw new ApiError(detail ?? `Request failed: ${response.status} ${response.statusText}`, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  health: (): Promise<HealthResponse> => request("/health"),

  version: (): Promise<VersionResponse> => request("/version"),

  analyze: (body: AnalyzeRequest, mock: boolean): Promise<AnalyzeResponse> =>
    request(mock ? "/analyze/mock" : "/analyze", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listReports: (limit = 50): Promise<ReportListItem[]> =>
    request(`/reports?limit=${encodeURIComponent(limit)}`),

  getReport: (reportId: string): Promise<ReportDetail> =>
    request(`/reports/${encodeURIComponent(reportId)}`),

  /** GET /download/{id} is not fetched as JSON - the browser navigates
   * to it directly (or an <a download> uses it) so the server's own
   * FileResponse / Content-Disposition handling does the work. This
   * just builds the correct, base-URL-aware URL for that.
   */
  downloadUrl: (reportId: string): string => `${getApiBaseUrl()}/download/${encodeURIComponent(reportId)}`,

  /** GET /analyze/stream is not fetched via request() above - it's an
   * SSE endpoint, consumed by the browser's native EventSource, which
   * takes a URL string and manages the connection/parsing itself
   * (never a JSON response body the way every other method here
   * returns). This still keeps URL construction in the one module
   * that's supposed to know it, rather than a component building
   * `${getApiBaseUrl()}/analyze/stream?...` itself.
   */
  streamUrl: (params: AnalyzeStreamParams): string => {
    const url = new URL(`${getApiBaseUrl()}/analyze/stream`);
    if (params.keyword) url.searchParams.set("keyword", params.keyword);
    if (params.source) url.searchParams.set("source", params.source);
    url.searchParams.set("limit", String(params.limit));
    url.searchParams.set("use_cache", String(params.use_cache));
    if (params.subreddit) url.searchParams.set("subreddit", params.subreddit);
    if (params.num_reports) url.searchParams.set("num_reports", String(params.num_reports));
    return url.toString();
  },
};
