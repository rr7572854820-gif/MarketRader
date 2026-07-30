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
  VersionResponse,
} from "@/lib/api/types";

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
};
