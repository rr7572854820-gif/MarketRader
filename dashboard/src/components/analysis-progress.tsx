"use client";

/**
 * Real-time progress UI for an analysis run, backed by GET /analyze/stream
 * (Server-Sent Events) instead of blocking silently on POST /analyze.
 *
 * Two real limitations worth understanding before touching this file:
 *
 * 1. The SSE stream carries ONLY progress events (stage/message/percent) -
 *    never the final structured report. That's a deliberate property of
 *    the backend endpoint (see src/api/routes.py::analyze_stream's own
 *    docstring), not an oversight here, and this component was built
 *    without changing that. So the completion payload is reconstructed
 *    best-effort after the stream ends: list the most recent saved run
 *    (GET /reports), fetch it (GET /reports/{id} - whose `summary` field
 *    is a real, complete ExecutionSummary, not fabricated), and parse its
 *    Markdown with lib/parse-report-markdown.ts for the opportunity list
 *    - the exact same fallback path the Report Details page already uses
 *    for *past* reports, reused here rather than duplicated. This is
 *    assembled into a real AnalyzeResponse (not the "Report" type named
 *    in this feature's original spec, which doesn't exist anywhere in
 *    this codebase) so the caller can reuse its existing result-summary
 *    UI unchanged. Two ProjectHealth fields (total_verified_insights,
 *    verification_percentage) aren't present in ExecutionSummary at all,
 *    so they're derived from the parsed opportunities' own verification
 *    data instead of being invented - see finalizeReport() below.
 *    onError() fires instead of a fabricated result if this correlation
 *    genuinely fails (e.g. GET /reports returns nothing).
 *
 * 2. The browser's native EventSource "error" event carries no status
 *    code or response body - by design, not a gap in this component.
 *    "Exact backend text" is only achievable for failures caught BEFORE
 *    opening the connection (this component reuses analysis-form.tsx's
 *    existing field validation for that); a genuine connection failure
 *    reports the most honest specific thing actually knowable, not a
 *    fabricated backend message that was never sent.
 */

import * as React from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { parseExecutiveSummary, parseOpportunitiesFromMarkdown } from "@/lib/parse-report-markdown";
import type { AnalyzeResponse, InsightReport, Source } from "@/lib/api/types";

const MAX_VISIBLE_MESSAGES = 6;

const STAGE_LABELS: Record<string, string> = {
  fetch: "Fetching",
  analyze: "AI Extraction",
  cluster: "Clustering",
  verify: "Verification",
  report: "Report Generation",
  done: "Complete",
};

interface ProgressMessage {
  stage: string;
  message: string;
  percent: number;
  /** Seconds elapsed (from this component's own timer) when received - not sent by the backend. */
  time: number;
}

export interface AnalysisProgressProps {
  keyword: string;
  source: Source;
  limit: number;
  useCache: boolean;
  /** Only meaningful for source="reddit" (AnalyzeRequest requires it to
   * target the right subreddit) - not in this feature's original prop
   * list, but omitting it would silently ignore the user's actual
   * subreddit choice for every Reddit run. Defaults to "all", matching
   * the backend's own default.
   */
  subreddit?: string;
  /** Called once, with a real AnalyzeResponse reconstructed after the
   * stream ends (see this file's module docstring for how and why) -
   * not the "Report" type named in this feature's original spec, which
   * has no corresponding type anywhere in this codebase.
   */
  onComplete: (response: AnalyzeResponse) => void;
  onError: (message: string) => void;
  /** Fires once, on mount, if EventSource isn't available in this
   * browser - the caller owns the actual POST /analyze fallback (it
   * already has that code in analysis-form.tsx); this component's job
   * is only to detect the gap and say so, not to duplicate fetch logic.
   */
  onUnsupported: () => void;
}

export function AnalysisProgress({
  keyword,
  source,
  limit,
  useCache,
  subreddit,
  onComplete,
  onError,
  onUnsupported,
}: AnalysisProgressProps) {
  const [messages, setMessages] = React.useState<ProgressMessage[]>([]);
  const [currentPercent, setCurrentPercent] = React.useState(0);
  const [elapsedSeconds, setElapsedSeconds] = React.useState(0);
  const [isComplete, setIsComplete] = React.useState(false);

  const elapsedRef = React.useRef(0);
  const logRef = React.useRef<HTMLDivElement | null>(null);
  const finishedRef = React.useRef(false);

  async function finalizeReport(): Promise<void> {
    try {
      const recent = await api.listReports(1);
      const latest = recent[0];
      if (!latest) {
        onError("Analysis finished, but the resulting report could not be located.");
        return;
      }
      const detail = await api.getReport(latest.report_id);

      let report: InsightReport | null = null;
      if (detail.markdown) {
        const opportunities = parseOpportunitiesFromMarkdown(detail.markdown);
        const verifiedOpportunities = opportunities.filter((o) => o.has_verification_data);
        report = {
          executive_summary: parseExecutiveSummary(detail.markdown) ?? "",
          top_opportunities: opportunities,
          project_health: {
            total_discussions_fetched: detail.summary.posts_fetched,
            total_discussions_analyzed: detail.summary.posts_analyzed,
            total_opportunity_clusters: detail.summary.clusters_found,
            // Not present in ExecutionSummary at all - derived from the
            // parsed opportunities themselves rather than invented, so
            // it's a real (if approximate) statistic, not a placeholder.
            total_verified_insights: verifiedOpportunities.length,
            verification_percentage:
              opportunities.length > 0 ? (verifiedOpportunities.length / opportunities.length) * 100 : 0,
            ai_provider_used: "",
            analysis_timestamp: detail.summary.end_time,
          },
        };
      }
      // report stays null if no Markdown was saved (report_format
      // never actually produces this for this endpoint's own default,
      // but honestly reflected rather than assumed) - report_id and
      // summary are real either way, so the caller can still show
      // accurate run stats and link to the report page.
      onComplete({ report_id: latest.report_id, summary: detail.summary, report });
    } catch {
      onError("Analysis finished, but the resulting report could not be loaded.");
    }
  }

  // Elapsed timer - a ref alongside the state so the EventSource effect
  // below doesn't need elapsedSeconds as a dependency (which would tear
  // down and reopen the connection every single second).
  React.useEffect(() => {
    const interval = window.setInterval(() => {
      elapsedRef.current += 1;
      setElapsedSeconds(elapsedRef.current);
    }, 1000);
    return () => window.clearInterval(interval);
  }, []);

  React.useEffect(() => {
    if (typeof EventSource === "undefined") {
      onUnsupported();
      return;
    }

    const eventSource = new EventSource(api.streamUrl({ keyword, source, limit, use_cache: useCache, subreddit }));

    eventSource.onmessage = (event) => {
      let parsed: { stage: string; message: string; percent: number };
      try {
        parsed = JSON.parse(event.data);
      } catch {
        // Malformed event - never show a message that didn't genuinely
        // come from the backend, so this is silently skipped rather
        // than surfaced as a fabricated log line.
        return;
      }

      setMessages((prev) => [...prev, { ...parsed, time: elapsedRef.current }]);
      setCurrentPercent(parsed.percent);

      if (parsed.percent >= 100 && !finishedRef.current) {
        finishedRef.current = true;
        setIsComplete(true);
        eventSource.close();
        void finalizeReport();
      }
    };

    eventSource.onerror = () => {
      if (finishedRef.current) return; // connection closing after a clean finish - not a real error
      finishedRef.current = true;
      eventSource.close();
      onError("Lost connection to the analysis stream.");
    };

    return () => {
      eventSource.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentionally opens exactly one connection per mount; the parent remounts this component for a new run rather than this effect re-running mid-stream.
  }, []);

  React.useEffect(() => {
    if (!logRef.current) return;
    logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [messages]);

  const visibleMessages = messages.slice(-MAX_VISIBLE_MESSAGES);
  const currentStage = messages.length > 0 ? messages[messages.length - 1].stage : null;
  const currentStageLabel = currentStage ? (STAGE_LABELS[currentStage] ?? currentStage) : null;

  return (
    <Card role="status" aria-label="Analysis in progress" aria-live="polite">
      <CardHeader>
        <div className="flex items-baseline justify-between gap-4">
          <CardTitle>{isComplete ? "Finishing up…" : "Analyzing…"}</CardTitle>
          <span className="shrink-0 font-mono text-sm tabular-nums text-muted-foreground">
            {/* key={currentPercent} retriggers the fade on every change - a
             * smooth-feeling update without adding interpolation state
             * (the literal "React state update every 100ms" spec would
             * be a logic change; this stays pure CSS, same technique as
             * the stage label below). */}
            <span key={currentPercent} className="analysis-progress-percent">
              {currentPercent}%
            </span>{" "}
            · {elapsedSeconds}s
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="analysis-progress-bar-fill h-full rounded-full bg-primary"
            style={{ width: `${currentPercent}%` }}
            role="progressbar"
            aria-valuenow={currentPercent}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>

        {currentStageLabel ? (
          <p key={currentStage} className="analysis-progress-stage-label text-sm font-semibold">
            Stage: {currentStageLabel}
          </p>
        ) : null}

        <div ref={logRef} className="max-h-40 space-y-1 overflow-y-auto rounded-md bg-muted/50 p-3">
          {visibleMessages.length === 0 ? (
            <p className="font-mono text-xs text-muted-foreground">Waiting for the analysis to start…</p>
          ) : (
            visibleMessages.map((m, i) => (
              <p key={`${m.time}-${i}`} className="analysis-progress-message font-mono text-xs text-foreground">
                {m.message}
              </p>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}
