"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Download, FileQuestion, Info } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ErrorState } from "@/components/error-state";
import { OpportunityCard } from "@/components/opportunity-card";
import { ReportDetailSkeleton } from "@/components/skeletons/report-detail-skeleton";
import { TopPainPointsChart } from "@/components/charts/top-pain-points-chart";
import { OpportunityScoresChart } from "@/components/charts/opportunity-scores-chart";
import { VerificationDistributionChart } from "@/components/charts/verification-distribution-chart";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { ExecutionSummary, OpportunityEntry, ReportDetail } from "@/lib/api/types";
import { parseExecutiveSummary, parseOpportunitiesFromMarkdown } from "@/lib/parse-report-markdown";
import { readCachedFreshReport } from "@/lib/report-cache";

function formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function ReportDetailPage() {
  const params = useParams<{ reportId: string }>();
  const reportId = params.reportId;

  const [detail, setDetail] = React.useState<ReportDetail | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<unknown>(null);

  // See app/reports/page.tsx's identical split for why fetchReport (no
  // synchronous setState) is what the mount effect calls, while retry
  // (synchronous setState, but from a button's onClick) is not.
  const fetchReport = React.useCallback(() => {
    api
      .getReport(reportId)
      .then(setDetail)
      .catch(setError)
      .finally(() => setIsLoading(false));
  }, [reportId]);

  const retry = React.useCallback(() => {
    setIsLoading(true);
    setError(null);
    fetchReport();
  }, [fetchReport]);

  React.useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  // Prefer the exact structured data from a just-completed run (cached
  // client-side in this tab), falling back to reconstructing it from
  // the saved Markdown for a report opened any other way - see
  // lib/parse-report-markdown.ts for why that fallback exists and its
  // limits.
  const { executiveSummary, opportunities, isParsedFromMarkdown } = React.useMemo(() => {
    const fresh = readCachedFreshReport(reportId);
    if (fresh) {
      return { executiveSummary: fresh.executive_summary, opportunities: fresh.top_opportunities, isParsedFromMarkdown: false };
    }
    if (detail?.markdown) {
      const opportunities: OpportunityEntry[] = parseOpportunitiesFromMarkdown(detail.markdown);
      return {
        executiveSummary: parseExecutiveSummary(detail.markdown),
        opportunities,
        isParsedFromMarkdown: true,
      };
    }
    return { executiveSummary: null, opportunities: [] as OpportunityEntry[], isParsedFromMarkdown: false };
  }, [detail, reportId]);

  if (isLoading) {
    return <ReportDetailSkeleton />;
  }

  if (error instanceof ApiError && error.isNotFound) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
          <FileQuestion className="size-10 text-muted-foreground" aria-hidden="true" />
          <p className="text-lg font-medium">Report not found</p>
          <p className="max-w-sm text-muted-foreground">
            No report exists with ID <span className="font-mono">{reportId}</span>. It may have been removed, or
            the ID in the URL is wrong.
          </p>
          <Button render={<Link href="/reports" />} nativeButton={false} variant="outline">
            <ArrowLeft className="size-4" /> Back to Reports
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return <ErrorState error={error} onRetry={retry} />;
  }

  if (!detail) {
    return null;
  }

  const { summary } = detail;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1.5">
          <Button render={<Link href="/reports" />} nativeButton={false} variant="ghost" size="sm" className="-ml-2.5">
            <ArrowLeft className="size-4" /> Back to Reports
          </Button>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-mono text-xl font-semibold tracking-tight sm:text-2xl">{reportId}</h1>
            <Badge
              variant="outline"
              className={
                summary.succeeded
                  ? "border-emerald-600/30 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400"
                  : "border-red-500/30 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-400"
              }
            >
              {summary.succeeded ? "Succeeded" : "Failed"}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            {formatTimestamp(summary.start_time)} · {summary.duration_seconds.toFixed(1)}s
          </p>
        </div>
        {detail.markdown ? (
          <Button render={<a href={api.downloadUrl(reportId)} download />} nativeButton={false} variant="outline">
            <Download className="size-4" /> Download Markdown
          </Button>
        ) : null}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Discussions fetched" value={summary.posts_fetched} />
        <StatTile label="Discussions analyzed" value={summary.posts_analyzed} />
        <StatTile label="Opportunities" value={summary.clusters_found} />
        <StatTile label="AI calls" value={summary.ai_calls_made} />
      </div>

      {summary.errors.length > 0 ? <RunNotes summary={summary} /> : null}

      <Card className="border-l-2 border-l-primary/40">
        <CardHeader>
          <CardTitle>Executive Summary</CardTitle>
        </CardHeader>
        <CardContent>
          {executiveSummary ? (
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">{executiveSummary}</p>
          ) : (
            <p className="text-sm text-muted-foreground">
              No executive summary is available for this run{detail.markdown ? "" : " (report_format was 'terminal', so no report file was saved)"}.
            </p>
          )}
        </CardContent>
      </Card>

      {isParsedFromMarkdown ? (
        <p className="text-xs text-muted-foreground">
          Opportunity details below were reconstructed from the saved report file (this report wasn&apos;t just run in
          this browser tab), so formatting may occasionally differ slightly from a freshly-run result.
        </p>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Charts</CardTitle>
          <CardDescription>Derived from this run&apos;s opportunity clusters.</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="pain-points">
            <TabsList>
              <TabsTrigger value="pain-points">Top Pain Points</TabsTrigger>
              <TabsTrigger value="scores">Opportunity Scores</TabsTrigger>
              <TabsTrigger value="verification">Verification Distribution</TabsTrigger>
            </TabsList>
            <TabsContent value="pain-points">
              <TopPainPointsChart opportunities={opportunities} />
            </TabsContent>
            <TabsContent value="scores">
              <OpportunityScoresChart opportunities={opportunities} />
            </TabsContent>
            <TabsContent value="verification">
              <VerificationDistributionChart opportunities={opportunities} />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <div className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight">Opportunities ({opportunities.length})</h2>
        {opportunities.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No opportunity data available to display for this run.
          </p>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {opportunities.map((opportunity, i) => (
              <OpportunityCard key={`${opportunity.title}-${i}`} opportunity={opportunity} rank={i + 1} />
            ))}
          </div>
        )}
        {opportunities.length > 0 ? (
          <p className="text-xs text-muted-foreground">
            Fields marked <Info className="inline size-3 align-[-1px]" aria-hidden="true" /> (opportunity score,
            target customer) are AI-inferred from discussion patterns, not verified findings.
          </p>
        ) : null}
      </div>
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <Card className="gap-1 rounded-lg py-3">
      <CardContent className="px-4">
        <p className="text-2xl font-semibold tabular-nums">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );
}

/** Same pattern as analysis-form.tsx's inline post-run summary (see its
 * own comment for the full evidence-integrity reasoning): a calm gray
 * ratio instead of a red error list, but never a dead end - the real
 * backend text stays reachable one click away via "Show details" so
 * this page and the inline summary never disagree about how much can
 * actually be seen, just how loudly it's presented by default.
 */
function RunNotes({ summary }: { summary: ExecutionSummary }) {
  const hasShortfall = summary.posts_analyzed < summary.posts_fetched;

  return (
    <div className="space-y-1.5">
      <p className="text-sm text-muted-foreground">
        {hasShortfall
          ? `${summary.posts_analyzed} of ${summary.posts_fetched} fetched discussions could be analyzed.`
          : `${summary.errors.length} note${summary.errors.length === 1 ? "" : "s"} from this run.`}
      </p>
      <details className="group">
        <summary className="cursor-pointer text-xs text-muted-foreground underline-offset-2 hover:underline">
          Show details
        </summary>
        <ul className="mt-2 list-inside list-disc space-y-1 font-mono text-xs text-muted-foreground">
          {summary.errors.map((message, i) => (
            <li key={i}>{message}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}
