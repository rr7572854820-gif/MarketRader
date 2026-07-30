import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ConfidenceBadge } from "@/components/confidence-badge";
import type { OpportunityEntry } from "@/lib/api/types";

const SPECULATIVE_LABEL = "SPECULATIVE - AI-inferred, not a verified finding";

/**
 * Renders exactly the fields Task 11 requires on the Report Details
 * page for one opportunity: opportunity score, confidence, verification
 * rate, supporting quotes, suggested customer segment, recommended next
 * action. Reused for both a freshly-completed analysis (Home page) and
 * a historical report (Report Details page) - same component, whether
 * the data came straight from POST /analyze or was reconstructed from
 * saved Markdown (see lib/parse-report-markdown.ts).
 */
export function OpportunityCard({ opportunity, rank }: { opportunity: OpportunityEntry; rank?: number }) {
  const verificationLabel = opportunity.has_verification_data
    ? `${Math.round(opportunity.verification_rate * 100)}% verified`
    : "No verification data available";

  return (
    <Card>
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <CardTitle className="text-balance text-base sm:text-lg">
            {rank ? <span className="text-muted-foreground">#{rank} </span> : null}
            {opportunity.title}
          </CardTitle>
          <ConfidenceBadge confidence={opportunity.confidence} />
        </div>
        <div className="flex flex-wrap gap-2 text-sm">
          <Badge variant="secondary" title={SPECULATIVE_LABEL}>
            Opportunity score: {opportunity.opportunity_score}/100*
          </Badge>
          <Badge variant="secondary">Frequency: {opportunity.frequency}</Badge>
          <Badge variant={opportunity.has_verification_data ? "secondary" : "outline"}>
            Verification rate: {verificationLabel}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div>
          <p className="font-medium text-foreground">Suggested customer segment*</p>
          <p className="text-muted-foreground">{opportunity.suggested_customer_segment || "Not specified."}</p>
        </div>

        <div>
          <p className="font-medium text-foreground">Recommended next action</p>
          <p className="text-muted-foreground">{opportunity.recommended_next_action}</p>
        </div>

        {opportunity.supporting_quotes.length > 0 ? (
          <div>
            <p className="font-medium text-foreground">Supporting quotes (independently verified)</p>
            <ul className="mt-1 space-y-2">
              {opportunity.supporting_quotes.map((quote, i) => (
                <li key={i} className="border-l-2 border-primary/40 pl-3 italic text-muted-foreground">
                  &ldquo;{quote}&rdquo;
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="text-muted-foreground">No supporting quotes were independently verified.</p>
        )}

        {opportunity.representative_discussions.length > 0 ? (
          <div>
            <p className="font-medium text-foreground">Representative discussions</p>
            <ul className="mt-1 space-y-1">
              {opportunity.representative_discussions.map((url) => (
                <li key={url}>
                  <a
                    href={url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="break-all text-primary underline underline-offset-2 hover:no-underline"
                  >
                    {url}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <p className="text-xs text-muted-foreground">* {SPECULATIVE_LABEL}.</p>
      </CardContent>
    </Card>
  );
}
