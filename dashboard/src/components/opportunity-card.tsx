import * as React from "react";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { OpportunityEntry } from "@/lib/api/types";

// ---------------------------------------------------------------------------
// Signal strength (replaces the old opportunity_score/ConfidenceBadge system
// entirely, per this task's explicit removal list). Computed from two real,
// already-available fields - frequency (independent mentions) and
// verification_rate (independent, zero-AI re-check, see
// src/verification/verifier.py) - never from opportunity_score, which is
// AI-inferred and no longer surfaced on this card at all.
// ---------------------------------------------------------------------------

type SignalTier = "strong" | "moderate" | "weak";

interface Signal {
  filled: number; // out of 5
  tier: SignalTier;
  label: string;
}

function computeSignal(frequency: number, verificationRate: number): Signal {
  if (frequency >= 5 && verificationRate >= 0.65) return { filled: 5, tier: "strong", label: "Strong signal" };
  if (frequency >= 3 && verificationRate >= 0.55) return { filled: 4, tier: "strong", label: "Strong signal" };
  if (frequency >= 2 && verificationRate >= 0.5) return { filled: 3, tier: "moderate", label: "Moderate signal" };
  if (frequency >= 1 && verificationRate >= 0.4) return { filled: 2, tier: "moderate", label: "Moderate signal" };
  return { filled: 1, tier: "weak", label: "Early signal" };
}

// Soft/token-based rather than the given literal hex - this card (unlike
// the landing page) sits under the app's real, working light/dark toggle,
// same resolution already recorded for the two prior opportunity-card
// redesigns this session (see SESSION.md).
const TIER_TEXT: Record<SignalTier, string> = {
  strong: "text-emerald-700 dark:text-emerald-400",
  moderate: "text-amber-700 dark:text-amber-400",
  weak: "text-muted-foreground",
};
const TIER_DOT: Record<SignalTier, string> = {
  strong: "bg-emerald-600 dark:bg-emerald-500",
  moderate: "bg-amber-600 dark:bg-amber-500",
  weak: "bg-muted-foreground/60",
};
const TIER_BORDER: Record<SignalTier, string> = {
  strong: "border-l-emerald-600/50 dark:border-l-emerald-700",
  moderate: "border-l-border",
  weak: "border-l-border",
};

function SignalDots({ signal }: { signal: Signal }) {
  return (
    <div className="flex shrink-0 flex-col items-end gap-1">
      <div className="flex gap-[3px]" role="img" aria-label={`${signal.label}: ${signal.filled} of 5`}>
        {Array.from({ length: 5 }).map((_, i) => (
          <span
            key={i}
            className={cn("size-2.5 rounded-full", i < signal.filled ? TIER_DOT[signal.tier] : "bg-muted")}
            aria-hidden="true"
          />
        ))}
      </div>
      <span className={cn("text-[11px] font-medium", TIER_TEXT[signal.tier])}>{signal.label}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Source counting - representative_discussions is a flat URL list with no
// per-quote correspondence (see the "best quote" section below for why that
// matters). Counts distinct GitHub repos as "repos"; falls back to the
// neutral "sources" wording whenever a discussion isn't a GitHub issue (a
// Hacker News thread isn't a "repo") rather than mislabeling it.
// ---------------------------------------------------------------------------

function discussionIdentity(url: string): { key: string; isGithub: boolean } {
  try {
    const parsed = new URL(url);
    if (parsed.hostname.includes("github.com")) {
      const [owner, repo] = parsed.pathname.split("/").filter(Boolean);
      return { key: owner && repo ? `${owner}/${repo}` : url, isGithub: true };
    }
    return { key: url, isGithub: false };
  } catch {
    return { key: url, isGithub: false };
  }
}

function summarizeSources(urls: string[]): { count: number; noun: string } {
  const identities = urls.map(discussionIdentity);
  const count = new Set(identities.map((d) => d.key)).size;
  const noun = identities.length > 0 && identities.every((d) => d.isGithub) ? "repos" : "sources";
  return { count, noun };
}

function stripProtocol(url: string): string {
  return url.replace(/^https?:\/\//, "");
}

// ---------------------------------------------------------------------------
// Quote keyword highlighting - pain-signal patterns only, on the quote's own
// real text. Never adds or infers words, only marks ones already present.
// ---------------------------------------------------------------------------

const HIGHLIGHT_PATTERN =
  /\b\d+\s*(?:hours?|weeks?|months?|days?|minutes?|years?)\b|\b(?:no|never|missing|broken|fails?|can'?t|unable)\b|\b(?:always|every time|constantly)\b|\b(?:painful|frustrated|impossible|terrible)\b/gi;

function highlightQuote(quote: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  const pattern = new RegExp(HIGHLIGHT_PATTERN);
  let key = 0;

  while ((match = pattern.exec(quote)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(<React.Fragment key={key++}>{quote.slice(lastIndex, match.index)}</React.Fragment>);
    }
    nodes.push(
      <mark key={key++} className="bg-transparent font-medium not-italic text-foreground/80">
        {match[0]}
      </mark>
    );
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < quote.length) {
    nodes.push(<React.Fragment key={key++}>{quote.slice(lastIndex)}</React.Fragment>);
  }
  return nodes;
}

// ---------------------------------------------------------------------------
// Customer tags - parsed from the same suggested_customer_segment string the
// old card rendered as a sentence, never fabricated from anything else.
// ---------------------------------------------------------------------------

const MAX_TAG_LENGTH = 20;
const MAX_TAGS = 3;

function parseCustomerTags(segment: string): string[] {
  if (!segment.trim()) return [];
  return segment
    .split(/\bor\b|\band\b|\/|,/i)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .map((part) => (part.length > MAX_TAG_LENGTH ? `${part.slice(0, MAX_TAG_LENGTH)}…` : part))
    .slice(0, MAX_TAGS);
}

// ---------------------------------------------------------------------------
// Footer action text - frequency-only, deliberately kept as short UI
// microcopy rather than a real recommendation engine. This is a real,
// named departure from recommended_next_action's verification-aware
// 5-branch decision table (src/reporting/report_generator.py) - confirmed
// via AskUserQuestion before building, see SESSION.md/TODO.md for the
// full tradeoff. Never claims "build" or "invest", consistent with that
// table's own hard constraint, even though it no longer reuses it.
// ---------------------------------------------------------------------------

function footerAction(frequency: number): { text: string; className: string } {
  if (frequency >= 3) return { text: "High priority — start interviews", className: TIER_TEXT.strong };
  if (frequency === 2) return { text: "Moderate — validate with 2 interviews", className: TIER_TEXT.moderate };
  return { text: "Early signal — monitor weekly", className: "text-muted-foreground" };
}

// ---------------------------------------------------------------------------
// Verify strip
// ---------------------------------------------------------------------------

function verifyStripContent(verificationRate: number): { text: string; className: string } {
  const percent = verificationRate * 100;
  if (percent >= 65) return { text: "Evidence independently verified against source text", className: TIER_TEXT.strong };
  if (percent >= 40)
    return { text: "Partially verified — review source links before acting", className: TIER_TEXT.moderate };
  return { text: "Low verification — treat as directional signal only", className: "text-muted-foreground" };
}

/**
 * One consistent structure for every opportunity: header (#rank of total +
 * signal dots) -> title -> signal bar -> story paragraph -> best quote
 * (others collapsed) -> verify strip -> footer (customer tags + action
 * text). Replaces the score/confidence-badge/SPECULATIVE-label version of
 * this card (see SESSION.md's 2026-08-07 redesign entries) - deliberate
 * full replacement per this task's explicit removal list, not an addition
 * alongside the old system.
 *
 * Reused for both a freshly-completed analysis and a historical report
 * (Report Details page) - same component regardless of whether the data
 * came straight from POST /analyze or was reconstructed from saved
 * Markdown (see lib/parse-report-markdown.ts).
 */
export function OpportunityCard({
  opportunity,
  rank,
  total,
}: {
  opportunity: OpportunityEntry;
  rank?: number;
  total?: number;
}) {
  const signal = computeSignal(opportunity.frequency, opportunity.verification_rate);
  const { count: sourceCount, noun: sourceNoun } = summarizeSources(opportunity.representative_discussions);
  const isWeakOpacity = opportunity.frequency === 1 && opportunity.verification_rate < 0.5;
  const isDimmedTitle = opportunity.frequency === 1;
  const tags = parseCustomerTags(opportunity.suggested_customer_segment);
  const action = footerAction(opportunity.frequency);
  const verifyStrip = verifyStripContent(opportunity.verification_rate);

  const bestQuote = opportunity.supporting_quotes[0];

  return (
    <Card className={cn("gap-0 overflow-hidden rounded-xl py-0", isWeakOpacity && "opacity-65")}>
      <CardHeader className="flex-row items-start justify-between gap-2 px-5 pt-5">
        {rank ? (
          <span className="text-sm font-medium text-muted-foreground">
            #{rank}
            {total ? ` of ${total}` : ""}
          </span>
        ) : (
          <span />
        )}
        <SignalDots signal={signal} />
      </CardHeader>

      <CardContent className="px-5 pt-3 pb-5">
        <h3
          className={cn(
            "mb-4 leading-[1.35] font-medium text-foreground",
            isDimmedTitle ? "text-[15px] text-muted-foreground" : "text-[17px]"
          )}
        >
          {opportunity.title}
        </h3>

        {/* Signal bar */}
        <p className="mb-3 text-xs text-muted-foreground">
          <span className={opportunity.frequency >= 3 ? TIER_TEXT.strong : undefined}>
            {opportunity.frequency} independent mention{opportunity.frequency === 1 ? "" : "s"}
          </span>{" "}
          · across {sourceCount} {sourceNoun} · {Math.round(opportunity.verification_rate * 100)}% verified
        </p>

        {/* Story paragraph - no "summary" field exists anywhere on
            OpportunityEntry (confirmed against lib/api/types.ts), so this
            always uses the given fallback formula, never a primary
            "summary field" branch that has nothing to read from. Doesn't
            restate frequency/source-count/verification - those already
            appear in the signal bar directly above this paragraph. */}
        <p
          className={cn(
            "mb-3 rounded-md border-l-2 bg-muted/30 p-3 text-[13px] leading-relaxed text-muted-foreground",
            TIER_BORDER[signal.tier]
          )}
        >
          {opportunity.frequency} developer{opportunity.frequency === 1 ? "" : "s"} reported this independently.
          {bestQuote ? " See quote below for the strongest evidence." : ""}
        </p>

        {/* Best quote only - no expand/collapse for additional quotes. */}
        {bestQuote ? (
          <div className="mb-3">
            <p className="text-[13px] leading-relaxed text-muted-foreground italic">
              &ldquo;{highlightQuote(bestQuote)}&rdquo;
            </p>
            <QuoteSource discussions={opportunity.representative_discussions} />
          </div>
        ) : null}
      </CardContent>

      {/* Verify strip - full width, deliberately outside CardContent's
          padding so it reaches the card edges. */}
      <div className={cn("border-t border-border/60 bg-muted/40 px-5 py-2.5 text-[11px]", verifyStrip.className)}>
        <span className={cn("mr-1.5 inline-block size-1.5 rounded-full align-middle", TIER_DOT[signal.tier])} />
        {verifyStrip.text}
      </div>

      {/* Footer row */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-5 py-3">
        <div className="flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <span
              key={tag}
              className="rounded border border-border/70 bg-muted/60 px-2 py-0.5 text-[11px] text-muted-foreground"
            >
              {tag}
            </span>
          ))}
        </div>
        <span className={cn("text-[11px] font-medium", action.className)}>{action.text}</span>
      </div>
    </Card>
  );
}

/** Only claims a specific quote-source URL when it's unambiguous (exactly
 * one representative discussion - a single-source cluster, where every
 * quote necessarily came from that one post). report_generator.py builds
 * supporting_quotes (across every VERIFIED field on every insight in the
 * cluster) and representative_discussions (one URL per insight) from
 * separate iteration orders with no index correspondence - for a
 * multi-source cluster, pairing quote[0] with url[0] would often be wrong.
 * A multi-source opportunity simply shows no source line rather than a
 * bulleted "N linked discussions" list (removed - broken rendering, and a
 * specific quote next to an unrelated bullet list of URLs implied the same
 * wrong per-quote attribution this component exists to avoid).
 */
function QuoteSource({ discussions }: { discussions: string[] }) {
  if (discussions.length !== 1) return null;

  return (
    <a
      href={discussions[0]}
      target="_blank"
      rel="noreferrer noopener"
      className="mt-1 block text-[11px] text-muted-foreground/70 hover:text-muted-foreground hover:underline"
    >
      {stripProtocol(discussions[0])}
    </a>
  );
}
