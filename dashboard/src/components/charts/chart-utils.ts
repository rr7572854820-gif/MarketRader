import type { OpportunityEntry } from "@/lib/api/types";

export function truncateLabel(label: string, max = 28): string {
  return label.length > max ? `${label.slice(0, max - 1)}…` : label;
}

/** Recharts needs a flat, small array to render sensibly - caps to the
 * top N by whatever the caller already sorted by, rather than every
 * chart trying to cram in an unbounded number of opportunities.
 */
export function topN<T>(items: T[], n = 8): T[] {
  return items.slice(0, n);
}

export function hasOpportunities(opportunities: OpportunityEntry[]): boolean {
  return opportunities.length > 0;
}
