/**
 * Reconstructs a best-effort OpportunityEntry[] from the raw Markdown
 * GET /reports/{id} returns, for pages viewing a *past* report.
 *
 * Why this exists (read this before touching it):
 * POST /analyze's response includes the full, structured InsightReport
 * (top_opportunities with real numbers) because it's still sitting in
 * the backend's memory right after the run. GET /reports/{id} cannot
 * do the same for a past run - the pipeline only ever persists an
 * InsightReport as rendered Markdown (or not at all, for
 * report_format="terminal"); it never writes a JSON form of the
 * structured report to disk. This is a deliberate, documented backend
 * decision (see SESSION.md's Task 10 entry, "Weaknesses"), not a bug -
 * and per Task 11's instructions, this frontend must not modify the
 * backend to change that without a true backend bug being found.
 *
 * So for a historical report, this Markdown text is the *only* source
 * of per-opportunity fields (score, confidence, verification rate,
 * quotes, segment, next action) available anywhere. This parser
 * reconstructs them from it, rather than the Report Details page
 * simply not showing per-opportunity cards/charts for anything except
 * a just-completed run.
 *
 * This is a real, load-bearing coupling to the *exact* text format
 * src/reporting/formatter.py::format_markdown() produces - a change to
 * that function's heading levels, bullet labels, or quote formatting
 * will silently break this parser. It is deliberately defensive, not
 * fragile-by-accident: every field extraction is independent and
 * optional, so a partial format change degrades individual fields
 * rather than throwing, and the Report Details page always shows the
 * raw Markdown too (never only the parsed view) so nothing is ever
 * hidden if parsing comes back empty or wrong. See the Task 11
 * architecture review in SESSION.md for the full tradeoff discussion -
 * this was the single biggest design decision in the dashboard.
 */

import type { ConfidenceLevel, OpportunityEntry } from "@/lib/api/types";

const CONFIDENCE_VALUES: ConfidenceLevel[] = ["Strong", "Moderate", "Weak"];

function parseConfidence(raw: string | undefined): ConfidenceLevel {
  const match = CONFIDENCE_VALUES.find((value) => value.toLowerCase() === raw?.trim().toLowerCase());
  return match ?? "Weak";
}

function parseVerificationRate(raw: string | undefined): { rate: number; hasData: boolean } {
  if (!raw || /no verification data available/i.test(raw)) {
    return { rate: 0, hasData: false };
  }
  const match = raw.match(/(\d+(?:\.\d+)?)\s*%/);
  return match ? { rate: Number(match[1]) / 100, hasData: true } : { rate: 0, hasData: false };
}

function extractField(block: string, label: string): string | undefined {
  // Matches "- **Label** *(...)*: value" or "- **Label**: value", to end of line.
  const pattern = new RegExp(`\\*\\*${label}\\*\\*(?:\\s*\\*\\([^)]*\\)\\*)?:\\s*(.+)`, "i");
  const match = block.match(pattern);
  return match?.[1]?.trim();
}

function extractQuotes(block: string): string[] {
  return Array.from(block.matchAll(/^>\s?(.+)$/gm)).map((m) => m[1].trim());
}

function extractDiscussionUrls(block: string): string[] {
  return Array.from(block.matchAll(/^-\s*<(.+)>$/gm)).map((m) => m[1].trim());
}

export function parseExecutiveSummary(markdown: string): string | null {
  const match = markdown.match(/## Executive Summary\s*\n+([\s\S]*?)(?=\n## )/);
  return match ? match[1].trim() : null;
}

export function parseOpportunitiesFromMarkdown(markdown: string): OpportunityEntry[] {
  const opportunitiesSection = markdown.match(/## Top Opportunities[^\n]*\n+([\s\S]*?)(?=\n## Project Health)/);
  if (!opportunitiesSection) {
    return [];
  }

  const blocks = opportunitiesSection[1]
    .split(/^### \d+\.\s*/m)
    .map((block) => block.trim())
    .filter(Boolean);

  return blocks.map((block): OpportunityEntry => {
    const firstLineBreak = block.indexOf("\n");
    const title = (firstLineBreak === -1 ? block : block.slice(0, firstLineBreak)).trim();

    const scoreRaw = extractField(block, "Opportunity score");
    const frequencyRaw = extractField(block, "Frequency");
    const { rate, hasData } = parseVerificationRate(extractField(block, "Verification rate"));

    return {
      title,
      opportunity_score: scoreRaw ? Number(scoreRaw.match(/[\d.]+/)?.[0] ?? 0) : 0,
      confidence: parseConfidence(extractField(block, "Confidence")),
      frequency: frequencyRaw ? Number(frequencyRaw.match(/\d+/)?.[0] ?? 0) : 0,
      verification_rate: rate,
      has_verification_data: hasData,
      supporting_quotes: extractQuotes(block),
      representative_discussions: extractDiscussionUrls(block),
      suggested_customer_segment: extractField(block, "Suggested customer segment") ?? "",
      recommended_next_action: extractField(block, "Recommended next action") ?? "",
    };
  });
}
