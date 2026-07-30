"use client";

import * as React from "react";
import Link from "next/link";
import { Loader2, PlayCircle } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ErrorState } from "@/components/error-state";
import { AnalysisResultSkeleton } from "@/components/skeletons/analysis-result-skeleton";
import { api } from "@/lib/api/client";
import type { AnalyzeResponse } from "@/lib/api/types";
import { getDefaultMockMode } from "@/lib/settings";
import { cacheFreshReport } from "@/lib/report-cache";
import { useClientValue } from "@/hooks/use-client-value";

const MIN_LIMIT = 1;
const MAX_LIMIT = 100;

interface FieldErrors {
  subreddit?: string;
  limit?: string;
}

function validate(subreddit: string, limitRaw: string): FieldErrors {
  const errors: FieldErrors = {};
  if (!subreddit.trim()) {
    errors.subreddit = "Subreddit must not be blank.";
  }
  const limit = Number(limitRaw);
  if (!Number.isInteger(limit) || limit < MIN_LIMIT || limit > MAX_LIMIT) {
    errors.limit = `Limit must be a whole number between ${MIN_LIMIT} and ${MAX_LIMIT}.`;
  }
  return errors;
}

export function AnalysisForm() {
  const [subreddit, setSubreddit] = React.useState("all");
  const [keyword, setKeyword] = React.useState("");
  const [limit, setLimit] = React.useState("25");
  const [useCache, setUseCache] = React.useState(true);

  // The Settings page's stored default only exists on the client, so
  // it's read via useClientValue (hydration-safe, no effect needed -
  // see hooks/use-client-value.ts) rather than useState+useEffect.
  // mockModeOverride tracks an explicit choice made on *this* page,
  // which should win once the user actually touches the switch.
  const syncedDefaultMockMode = useClientValue(getDefaultMockMode, true);
  const [mockModeOverride, setMockModeOverride] = React.useState<boolean | null>(null);
  const mockMode = mockModeOverride ?? syncedDefaultMockMode;

  const [fieldErrors, setFieldErrors] = React.useState<FieldErrors>({});

  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [result, setResult] = React.useState<AnalyzeResponse | null>(null);
  const [error, setError] = React.useState<unknown>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    // Belt-and-suspenders against duplicate submissions: the button is
    // already disabled while isSubmitting, but a guard here protects
    // against a form re-submit triggered another way (e.g. pressing
    // Enter while React hasn't re-rendered the disabled state yet).
    if (isSubmitting) return;

    const errors = validate(subreddit, limit);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const response = await api.analyze(
        {
          subreddit: subreddit.trim(),
          keyword: keyword.trim() || null,
          limit: Number(limit),
          use_cache: useCache,
          report_format: "both",
        },
        mockMode
      );
      setResult(response);
      if (response.report_id && response.report) {
        cacheFreshReport(response.report_id, response.report);
      }
      if (!response.summary.succeeded) {
        toast.error("Analysis finished with errors - see details below.");
      } else {
        toast.success("Analysis complete.");
      }
    } catch (err) {
      setError(err);
      toast.error("Analysis failed to run.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Run an analysis</CardTitle>
          <CardDescription>
            Runs the MarketRadar pipeline (Fetch → Analyze → Cluster → Verify → Report) through the API. Mock mode
            is fully offline and free; turn it off to use real Reddit/Gemini data if the backend is configured for
            it.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="subreddit">Subreddit</Label>
                <Input
                  id="subreddit"
                  value={subreddit}
                  onChange={(e) => setSubreddit(e.target.value)}
                  placeholder="startups"
                  disabled={isSubmitting}
                  aria-invalid={Boolean(fieldErrors.subreddit)}
                  aria-describedby={fieldErrors.subreddit ? "subreddit-error" : undefined}
                />
                {fieldErrors.subreddit ? (
                  <p id="subreddit-error" className="text-sm text-destructive">
                    {fieldErrors.subreddit}
                  </p>
                ) : (
                  <p className="text-sm text-muted-foreground">Ignored in mock mode, but still required.</p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="keyword">Keyword (optional)</Label>
                <Input
                  id="keyword"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  placeholder="invoicing"
                  disabled={isSubmitting}
                />
                <p className="text-sm text-muted-foreground">Only include posts/comments containing this keyword.</p>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="limit">Post limit</Label>
                <Input
                  id="limit"
                  type="number"
                  min={MIN_LIMIT}
                  max={MAX_LIMIT}
                  value={limit}
                  onChange={(e) => setLimit(e.target.value)}
                  disabled={isSubmitting}
                  aria-invalid={Boolean(fieldErrors.limit)}
                  aria-describedby={fieldErrors.limit ? "limit-error" : undefined}
                />
                {fieldErrors.limit ? (
                  <p id="limit-error" className="text-sm text-destructive">
                    {fieldErrors.limit}
                  </p>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    {MIN_LIMIT}-{MAX_LIMIT}. Capped by the API regardless of what&apos;s requested here.
                  </p>
                )}
              </div>

              <div className="flex flex-col justify-center gap-4 sm:flex-row sm:items-center sm:justify-start sm:gap-8">
                <div className="flex items-center gap-2">
                  <Switch id="use-cache" checked={useCache} onCheckedChange={setUseCache} disabled={isSubmitting} />
                  <Label htmlFor="use-cache" className="font-normal">
                    Use cache
                  </Label>
                </div>
                <div className="flex items-center gap-2">
                  <Switch id="mock-mode" checked={mockMode} onCheckedChange={setMockModeOverride} disabled={isSubmitting} />
                  <Label htmlFor="mock-mode" className="font-normal">
                    Mock mode
                  </Label>
                </div>
              </div>
            </div>

            <Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
              {isSubmitting ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Running analysis…
                </>
              ) : (
                <>
                  <PlayCircle className="size-4" aria-hidden="true" /> Run Analysis
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {isSubmitting ? <AnalysisResultSkeleton /> : null}

      {!isSubmitting && error ? <ErrorState error={error} onRetry={() => setError(null)} /> : null}

      {!isSubmitting && result ? <AnalysisResultSummary result={result} /> : null}
    </div>
  );
}

function AnalysisResultSummary({ result }: { result: AnalyzeResponse }) {
  const { summary, report_id } = result;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {summary.succeeded ? "Analysis complete" : "Analysis finished with errors"}
        </CardTitle>
        <CardDescription>
          {summary.duration_seconds.toFixed(1)}s · {summary.posts_fetched} fetched · {summary.posts_analyzed}{" "}
          analyzed · {summary.clusters_found} opportunity cluster(s) · {summary.ai_calls_made} AI call(s) (
          {summary.cache_hits} cache hit(s))
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {summary.errors.length > 0 ? (
          <ul className="list-inside list-disc space-y-1 text-sm text-destructive">
            {summary.errors.map((message, i) => (
              <li key={i}>{message}</li>
            ))}
          </ul>
        ) : null}

        {report_id ? (
          <Button render={<Link href={`/reports/${report_id}`} />} nativeButton={false}>View full report</Button>
        ) : (
          <p className="text-sm text-muted-foreground">
            This run could not be matched back to a saved report file - see the summary above for what happened.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
