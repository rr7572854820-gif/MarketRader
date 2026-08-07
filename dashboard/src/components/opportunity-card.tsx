import { Info } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ConfidenceBadge } from "@/components/confidence-badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { ConfidenceLevel, OpportunityEntry } from "@/lib/api/types";

const SPECULATIVE_TOOLTIP =
  "AI-inferred from discussion patterns, not a verified finding - treat as a starting hypothesis, not a fact.";

// Confidence drives the recommended-action accent color, independent of
// the (unrelated) opportunity_score number - see confidence-badge.tsx
// for why confidence reflects how directly the evidence was stated, not
// how large the opportunity looks.
const ACTION_ACCENT: Record<ConfidenceLevel, string> = {
  Strong: "border-l-emerald-500",
  Moderate: "border-l-amber-500",
  Weak: "border-l-red-500",
};

type DiscussionSource = "github" | "hackernews" | "other";

function sourceOf(url: string): DiscussionSource {
  try {
    const hostname = new URL(url).hostname;
    if (hostname.includes("github.com")) return "github";
    if (hostname.includes("ycombinator.com")) return "hackernews";
    return "other";
  } catch {
    return "other";
  }
}

// "https://github.com/owner/repo/issues/93" -> "owner/repo #93" - real
// GitHub issue URL shape (see src/fetchers/github_fetcher.py's
// html_url). "https://news.ycombinator.com/item?id=123" -> "HN #123" -
// real HN item URL shape (src/fetchers/hn_fetcher.py). Falls back to
// the bare hostname for anything else rather than guessing a format.
function formatDiscussionLabel(url: string): string {
  try {
    const parsed = new URL(url);
    if (parsed.hostname.includes("github.com")) {
      const [owner, repo, , issueNumber] = parsed.pathname.split("/").filter(Boolean);
      if (owner && repo && issueNumber) return `${owner}/${repo} #${issueNumber}`;
    }
    if (parsed.hostname.includes("ycombinator.com")) {
      const id = parsed.searchParams.get("id");
      if (id) return `HN #${id}`;
    }
    return parsed.hostname;
  } catch {
    return url;
  }
}

// Card-level "Sources" pills, derived from the real discussion URLs
// this opportunity is backed by - not per-quote, since
// OpportunityEntry.supporting_quotes carries no field linking a
// specific quote back to the source it came from (see AskUserQuestion
// resolution for this task: fabricating that link per-quote would
// misattribute evidence, which this project treats as a real
// evidentiary-integrity violation, not a cosmetic shortcut).
function deriveSources(urls: string[]): Exclude<DiscussionSource, "other">[] {
  const seen = new Set<Exclude<DiscussionSource, "other">>();
  for (const url of urls) {
    const source = sourceOf(url);
    if (source !== "other") seen.add(source);
  }
  return Array.from(seen);
}

const SOURCE_LABEL: Record<Exclude<DiscussionSource, "other">, string> = {
  github: "github",
  hackernews: "hackernews",
};

function SpeculativeInfo() {
  return (
    <Tooltip>
      <TooltipTrigger
        className="inline-flex size-3.5 shrink-0 items-center justify-center rounded-full text-muted-foreground hover:text-foreground"
        aria-label="Why this field is AI-inferred"
      >
        <Info className="size-3.5" aria-hidden="true" />
      </TooltipTrigger>
      <TooltipContent>{SPECULATIVE_TOOLTIP}</TooltipContent>
    </Tooltip>
  );
}

/**
 * Renders exactly the fields Task 11 requires on the Report Details
 * page for one opportunity: opportunity score, confidence, verification
 * rate, supporting quotes, suggested customer segment, recommended next
 * action. Reused for both a freshly-completed analysis (Home page) and
 * a historical report (Report Details page) - same component, whether
 * the data came straight from POST /analyze or was reconstructed from
 * saved Markdown (see lib/parse-report-markdown.ts).
 *
 * Speculative fields (opportunity score, customer segment) keep an
 * inline info-icon tooltip each rather than a repeated paragraph
 * disclaimer per card - the shared explanation now lives once, as a
 * page-level footer note (see reports/[reportId]/page.tsx), same
 * information, shown once instead of once per card.
 */
export function OpportunityCard({ opportunity, rank }: { opportunity: OpportunityEntry; rank?: number }) {
  const verificationLabel = opportunity.has_verification_data
    ? `${Math.round(opportunity.verification_rate * 100)}% verified`
    : "No verification data";
  const sources = deriveSources(opportunity.representative_discussions);

  return (
    <Card className="gap-4 rounded-xl py-6">
      <CardHeader className="gap-2">
        <div className="flex items-start justify-between gap-2">
          {rank ? <span className="text-sm font-medium text-muted-foreground">#{rank}</span> : <span />}
          <ConfidenceBadge confidence={opportunity.confidence} />
        </div>
        <CardTitle className="line-clamp-2 text-base font-medium">{opportunity.title}</CardTitle>
        <div className="flex flex-wrap gap-1.5 pt-1 text-xs">
          <Badge variant="outline" className="gap-1 font-normal">
            Opportunity: {opportunity.opportunity_score}/100
            <SpeculativeInfo />
          </Badge>
          <Badge variant="outline" className="font-normal">
            Freq: {opportunity.frequency}
          </Badge>
          <Badge variant="outline" className="font-normal">
            {verificationLabel}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="space-y-0.5">
          <p className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
            Target customer
            <SpeculativeInfo />
          </p>
          <p className="text-foreground">{opportunity.suggested_customer_segment || "Not specified."}</p>
        </div>

        <div
          className={cn(
            "space-y-0.5 rounded-md border-l-2 bg-muted/40 px-3 py-2",
            ACTION_ACCENT[opportunity.confidence]
          )}
        >
          <p className="text-xs font-medium text-muted-foreground">Recommended action</p>
          <p className="text-foreground">{opportunity.recommended_next_action}</p>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-medium text-muted-foreground">Verified evidence</p>
            {sources.length > 0 ? (
              <div className="flex gap-1">
                {sources.map((source) => (
                  <Badge key={source} variant="outline" className="font-normal">
                    {SOURCE_LABEL[source]}
                  </Badge>
                ))}
              </div>
            ) : null}
          </div>
          {opportunity.supporting_quotes.length > 0 ? (
            <ul className="space-y-2">
              {opportunity.supporting_quotes.map((quote, i) => (
                <li
                  key={i}
                  className="rounded-r-md border-l-2 border-border bg-muted/30 px-3 py-2 text-[13px] text-muted-foreground"
                >
                  &ldquo;{quote}&rdquo;
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground">No supporting quotes were independently verified.</p>
          )}
        </div>

        {opportunity.representative_discussions.length > 0 ? (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Representative discussions</p>
            <ul className="space-y-1">
              {opportunity.representative_discussions.map((url) => (
                <li key={url}>
                  <a
                    href={url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="text-primary underline-offset-2 hover:underline"
                  >
                    {formatDiscussionLabel(url)}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
