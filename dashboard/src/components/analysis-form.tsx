"use client";

import * as React from "react";
import Link from "next/link";
import { Loader2, PlayCircle } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ErrorState } from "@/components/error-state";
import { AnalysisResultSkeleton } from "@/components/skeletons/analysis-result-skeleton";
import { AnalysisProgress } from "@/components/analysis-progress";
import { api } from "@/lib/api/client";
import type { AnalyzeRequest, AnalyzeResponse, ExecutionSummary, Source } from "@/lib/api/types";
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
    // Not a "must look like a technical keyword" check - any natural-
    // language description works now (Pipeline.run() runs it through
    // AI-assisted extract_search_terms before searching GitHub, see
    // src/insights/keyword_extraction.py). This is the one thing that
    // still can't be relaxed: the backend requires a non-blank value
    // for source="github" (AnalyzeRequest's model_validator) since
    // there's nothing to extract search terms from otherwise - kept
    // here so that's a friendly inline message instead of a raw 422.
    errors.keyword = "Tell MarketRadar what you're looking for - it can be a full sentence.";
  }
  const limit = Number(limitRaw);
  if (!Number.isInteger(limit) || limit < MIN_LIMIT || limit > MAX_LIMIT) {
    errors.limit = `Limit must be a whole number between ${MIN_LIMIT} and ${MAX_LIMIT}.`;
  }
  return errors;
}

export function AnalysisForm() {
  // Reddit is hidden from the Source toggle below (UI-only - the
  // backend/API/pipeline/fetcher factory all still fully support
  // source="reddit", see the TabsList below), so the default can't
  // stay "reddit": that would boot the form with the Subreddit input
  // and Mock mode switch visible (both gated on source === "reddit")
  // with no visible tab explaining why. "github" is the first
  // still-visible option.
  const [source, setSource] = React.useState<Source>("github");
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

  // "idle" | "streaming" (real-time SSE progress UI) | "post" (the
  // original blocking POST /analyze path, used both as the resting
  // fallback and while a run is actually happening on that path).
  const [runMode, setRunMode] = React.useState<"idle" | "streaming" | "post">("idle");
  const isSubmitting = runMode !== "idle";
  const [result, setResult] = React.useState<AnalyzeResponse | null>(null);
  const [error, setError] = React.useState<unknown>(null);

  function buildPayload(): AnalyzeRequest {
    // GitHub/HackerNews have no mock equivalent (force_mock always
    // returns Reddit's MockFetcher regardless of source - see
    // src/fetchers/__init__.py), so a run against either always hits
    // the real POST /analyze endpoint.
    return source === "github" || source === "hackernews"
      ? {
          source,
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
  }

  function handleAnalysisComplete(response: AnalyzeResponse) {
    setResult(response);
    if (response.report_id && response.report) {
      cacheFreshReport(response.report_id, response.report);
    }
    if (!response.summary.succeeded) {
      toast.error("Analysis finished with errors - see details below.");
    } else {
      toast.success("Analysis complete.");
    }
    setRunMode("idle");
  }

  function handleAnalysisError(err: unknown) {
    setError(err);
    toast.error("Analysis failed to run.");
    setRunMode("idle");
  }

  async function runViaPost() {
    setRunMode("post");
    try {
      const response = await api.analyze(buildPayload(), source === "github" || source === "hackernews" ? false : mockMode);
      handleAnalysisComplete(response);
    } catch (err) {
      handleAnalysisError(err);
    }
  }

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

    setError(null);
    setResult(null);

    // GET /analyze/stream has no mock variant (see
    // src/api/routes.py::analyze_stream's own docstring) - a mock-mode
    // Reddit run keeps using the existing, near-instant POST
    // /analyze/mock path instead of silently ignoring the user's mock
    // toggle by streaming a real/auto run in its place. EventSource is
    // also only ever checked here, inside this event handler - never in
    // render, which would risk a server/client hydration mismatch since
    // EventSource doesn't exist during server rendering at all.
    const shouldStream = source === "github" || source === "hackernews" || !mockMode;
    if (!shouldStream || typeof EventSource === "undefined") {
      await runViaPost();
      return;
    }

    setRunMode("streaming");
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
                  {/* Reddit hidden from the dashboard UI only - source="reddit"
                      stays fully supported everywhere else (backend, API,
                      pipeline, fetcher factory all untouched). Re-add this
                      TabsTrigger to bring it back. */}
                  {/* <TabsTrigger value="reddit" disabled={isSubmitting}>
                    Reddit
                  </TabsTrigger> */}
                  <TabsTrigger value="github" disabled={isSubmitting}>
                    GitHub
                  </TabsTrigger>
                  <TabsTrigger value="hackernews" disabled={isSubmitting}>
                    HackerNews
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
                <Label htmlFor="keyword">
                  {source === "github" || source === "hackernews" ? "What are you looking for?" : "Keyword (optional)"}
                </Label>
                <Input
                  id="keyword"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  placeholder={
                    source === "github" ? "e.g. I keep hearing people complain about invoice automation" : "invoicing"
                  }
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
                      ? "Describe what you're looking for in plain English. MarketRadar will find the right repositories."
                      : source === "hackernews"
                        ? "MarketRadar will search HackerNews discussions for this topic."
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

      {runMode === "streaming" ? (
        <AnalysisProgress
          keyword={keyword.trim()}
          source={source}
          limit={Number(limit)}
          useCache={useCache}
          subreddit={subreddit.trim()}
          onComplete={handleAnalysisComplete}
          onError={(message) => {
            // A lost/failed SSE connection falls back to the existing,
            // reliable POST /analyze path rather than just leaving the
            // user stuck - but the real reason is still shown, not
            // swallowed, since exact backend/connection text matters.
            toast.error(message);
            void runViaPost();
          }}
          onUnsupported={() => void runViaPost()}
        />
      ) : null}

      {runMode === "post" ? <AnalysisResultSkeleton /> : null}

      {!isSubmitting && error ? <ErrorState error={error} onRetry={() => setError(null)} /> : null}

      {!isSubmitting && result ? (
        <AnalysisResultSummary
          result={result}
          onTrySuggestion={(suggestion) => {
            setKeyword(suggestion);
            setResult(null);
          }}
        />
      ) : null}
    </div>
  );
}

const TOPIC_SUGGESTIONS = ["invoicing", "payments", "authentication"];

/** Evidence-integrity note (see CLAUDE.md §5, "never silently drop
 * uncertainty"): this summary never hides *that* some discussions
 * failed to analyze - it only avoids leading with a raw, technical,
 * URL-filled error list. The real success ratio is always shown in
 * plain language, and the underlying backend error strings stay one
 * click away via the "Show details" disclosure below, never deleted.
 * A shortfall is never relabeled as an intentional "quality filter" -
 * nothing was filtered; some extractions genuinely failed, and saying
 * so plainly is what lets a founder judge how much to trust the result.
 */
function AnalysisResultSummary({
  result,
  onTrySuggestion,
}: {
  result: AnalyzeResponse;
  onTrySuggestion: (keyword: string) => void;
}) {
  const { summary, report_id } = result;
  const hasShortfall = summary.posts_analyzed < summary.posts_fetched;
  const foundNothing = summary.clusters_found === 0;

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
        ) : null}

        {foundNothing ? <EmptyResultState summary={summary} onTrySuggestion={onTrySuggestion} /> : null}

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

/** Deliberately two different messages, not one generic "no results" -
 * conflating "genuinely nothing matched this topic" with "discussions
 * were found but analysis couldn't complete" would give wrong advice
 * in the second case (steering toward a different keyword when the
 * real cause might be, say, a temporarily unavailable AI provider -
 * see the "Show details" disclosure above for what actually happened).
 */
function EmptyResultState({
  summary,
  onTrySuggestion,
}: {
  summary: ExecutionSummary;
  onTrySuggestion: (keyword: string) => void;
}) {
  const nothingFetched = summary.posts_fetched === 0;

  return (
    <div className="space-y-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-3">
      <p className="text-sm text-foreground">
        {nothingFetched
          ? "No discussions found for this topic."
          : `Found ${summary.posts_fetched} discussion(s), but none could be turned into a verified opportunity - this may be a temporary issue rather than a sign there's nothing here (see details above).`}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">Try:</span>
        {TOPIC_SUGGESTIONS.map((topic) => (
          <Badge
            key={topic}
            variant="outline"
            render={<button type="button" onClick={() => onTrySuggestion(topic)} />}
            className="cursor-pointer hover:bg-muted"
          >
            {topic}
          </Badge>
        ))}
      </div>
    </div>
  );
}
