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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ErrorState } from "@/components/error-state";
import { AnalysisResultSkeleton } from "@/components/skeletons/analysis-result-skeleton";
import { api } from "@/lib/api/client";
import type { AnalyzeRequest, AnalyzeResponse, Source } from "@/lib/api/types";
import { getDefaultMockMode } from "@/lib/settings";
import { cacheFreshReport } from "@/lib/report-cache";
import { useClientValue } from "@/hooks/use-client-value";

const MIN_LIMIT = 1;
const MAX_LIMIT = 100;

interface FieldErrors {
  subreddit?: string;
  keyword?: string;
  limit?: string;
}

function validate(source: Source, subreddit: string, keyword: string, limitRaw: string): FieldErrors {
  const errors: FieldErrors = {};
  if (source === "reddit") {
    if (!subreddit.trim()) {
      errors.subreddit = "Subreddit must not be blank.";
    }
  } else if (!keyword.trim()) {
    // GitHubFetcher discovers repos from the keyword itself (GitHub
    // Search API) - there is no separate repo input anymore, so a
    // keyword is required, not optional, for this source.
    errors.keyword = "Keyword is required for GitHub source - MarketRadar uses it to find repositories.";
  }
  const limit = Number(limitRaw);
  if (!Number.isInteger(limit) || limit < MIN_LIMIT || limit > MAX_LIMIT) {
    errors.limit = `Limit must be a whole number between ${MIN_LIMIT} and ${MAX_LIMIT}.`;
  }
  return errors;
}

export function AnalysisForm() {
  const [source, setSource] = React.useState<Source>("reddit");
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

    const errors = validate(source, subreddit, keyword, limit);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setResult(null);

    // GitHub has no mock equivalent (force_mock always returns Reddit's
    // MockFetcher regardless of source - see src/fetchers/__init__.py),
    // so a GitHub run always hits the real POST /analyze endpoint.
    const payload: AnalyzeRequest =
      source === "github"
        ? {
            source: "github",
            keyword: keyword.trim(),
            limit: Number(limit),
            use_cache: useCache,
            report_format: "both",
          }
        : {
            subreddit: subreddit.trim(),
            keyword: keyword.trim() || null,
            limit: Number(limit),
            use_cache: useCache,
            report_format: "both",
          };

    try {
      const response = await api.analyze(payload, source === "github" ? false : mockMode);
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
            <div className="space-y-1.5">
              <Label>Source</Label>
              <Tabs
                value={source}
                onValueChange={(value) => setSource(value as Source)}
              >
                <TabsList>
                  <TabsTrigger value="reddit" disabled={isSubmitting}>
                    Reddit
                  </TabsTrigger>
                  <TabsTrigger value="github" disabled={isSubmitting}>
                    GitHub
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {source === "reddit" ? (
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
              ) : null}

              <div className="space-y-1.5">
                <Label htmlFor="keyword">{source === "github" ? "Keyword" : "Keyword (optional)"}</Label>
                <Input
                  id="keyword"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  placeholder={source === "github" ? "invoicing, AI coding tools, developer productivity" : "invoicing"}
                  disabled={isSubmitting}
                  aria-invalid={Boolean(fieldErrors.keyword)}
                  aria-describedby={fieldErrors.keyword ? "keyword-error" : undefined}
                />
                {fieldErrors.keyword ? (
                  <p id="keyword-error" className="text-sm text-destructive">
                    {fieldErrors.keyword}
                  </p>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    {source === "github"
                      ? "MarketRadar will automatically find the most relevant GitHub repositories for this topic."
                      : "Only include posts/comments containing this keyword."}
                  </p>
                )}
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
                {source === "reddit" ? (
                  <div className="flex items-center gap-2">
                    <Switch id="mock-mode" checked={mockMode} onCheckedChange={setMockModeOverride} disabled={isSubmitting} />
                    <Label htmlFor="mock-mode" className="font-normal">
                      Mock mode
                    </Label>
                  </div>
                ) : null}
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
