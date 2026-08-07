import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ConfidenceLevel } from "@/lib/api/types";

// Soft, bordered pills rather than solid fills - reads as "premium/
// muted" in both themes instead of a loud solid-color chip, while
// keeping the confidence level unambiguous at a glance.
const STYLES: Record<ConfidenceLevel, string> = {
  Strong:
    "border-emerald-600/30 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400",
  Moderate:
    "border-amber-500/30 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-400",
  Weak: "border-red-500/30 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-400",
};

export function ConfidenceBadge({ confidence, className }: { confidence: ConfidenceLevel; className?: string }) {
  return (
    <Badge className={cn(STYLES[confidence], className)} title="Confidence reflects how directly the evidence was stated - not how large the opportunity is.">
      {confidence} confidence
    </Badge>
  );
}
