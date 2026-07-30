/**
 * Caches a just-completed analysis's full structured InsightReport in
 * sessionStorage, keyed by report_id, so navigating straight from the
 * Home page to /reports/{id} can show the real structured data
 * (opportunity cards + charts) instead of falling back to parsing the
 * saved Markdown - see lib/parse-report-markdown.ts's module docstring
 * for why that fallback exists at all and why this cache is worth
 * having. This never talks to the backend and never invents data: it
 * only remembers, for this browser tab, the exact JSON POST /analyze
 * already returned.
 */

import type { InsightReport } from "@/lib/api/types";

function key(reportId: string): string {
  return `marketradar:fresh-report:${reportId}`;
}

export function cacheFreshReport(reportId: string, report: InsightReport): void {
  try {
    window.sessionStorage.setItem(key(reportId), JSON.stringify(report));
  } catch {
    // sessionStorage can throw in private-browsing/storage-full edge
    // cases - losing this cache just means Report Details falls back
    // to parsing Markdown, never a hard failure, so it's safe to ignore.
  }
}

export function readCachedFreshReport(reportId: string): InsightReport | null {
  try {
    const raw = window.sessionStorage.getItem(key(reportId));
    return raw ? (JSON.parse(raw) as InsightReport) : null;
  } catch {
    return null;
  }
}
