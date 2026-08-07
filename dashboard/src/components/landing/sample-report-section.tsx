import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ConfidenceBadge } from "@/components/confidence-badge";

/** Illustrative only - not a real, saved MarketRadar report (see this
 * section's own "Sample" label below, and CLAUDE.md's evidence-
 * integrity rules, which this page's own fake data must not quietly
 * violate any more than the product itself would). The real report
 * this mirrors the shape of is OpportunityCard (components/opportunity-card.tsx) -
 * reusing the same ConfidenceBadge/Card/Badge components here so a
 * visitor's first look at "what a report looks like" is visually
 * identical to a real one, just clearly marked as a mockup.
 */
const SAMPLE_OPPORTUNITIES = [
  {
    rank: 1,
    title: "European companies cannot issue invoices before payment is received",
    score: 85,
    verification: 71,
    quote:
      "When you issue an invoice in Europe it has to be paid or else you need to add a credit invoice to make up the balance.",
    source: "github.com/invoiceninja",
  },
  {
    rank: 2,
    title: "Manual reconciliation takes 4+ hours every week",
    score: 80,
    verification: 60,
    quote: "Bank reconciliation is the most painful part of my week.",
    source: "news.ycombinator.com",
  },
];

export function SampleReportSection() {
  return (
    <section id="sample-report" className="mx-auto max-w-4xl px-4 py-20 sm:py-28">
      <h2 className="text-balance text-center text-3xl font-semibold tracking-tight sm:text-4xl">
        What a report looks like
      </h2>

      <div className="mt-14 rounded-xl border border-white/10 bg-card/50 p-5 sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <Badge variant="outline" className="mb-2">
              Sample report - illustrative example
            </Badge>
            <h3 className="text-lg font-medium">Invoice automation</h3>
          </div>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          24 fetched · 10 analyzed · 7 opportunities found · under a minute
        </p>

        <div className="mt-6 space-y-4">
          {SAMPLE_OPPORTUNITIES.map((o) => (
            <Card key={o.rank}>
              <CardHeader className="gap-2">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <CardTitle className="text-balance text-base sm:text-lg">
                    <span className="text-muted-foreground">#{o.rank} </span>
                    {o.title}
                  </CardTitle>
                  <ConfidenceBadge confidence="Strong" />
                </div>
                <div className="flex flex-wrap gap-2 text-sm">
                  <Badge variant="secondary">Opportunity score: {o.score}/100*</Badge>
                  <Badge variant="secondary">Verification: {o.verification}% verified</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <p className="border-l-2 border-primary/40 pl-3 italic text-muted-foreground">
                  &ldquo;{o.quote}&rdquo;
                </p>
                <p className="text-xs text-muted-foreground">Source: {o.source}</p>
              </CardContent>
            </Card>
          ))}
        </div>
        <p className="mt-4 text-xs text-muted-foreground">* Speculative - AI-inferred, not a verified finding.</p>
      </div>
    </section>
  );
}
