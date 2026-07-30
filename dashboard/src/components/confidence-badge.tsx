import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ConfidenceLevel } from "@/lib/api/types";

const STYLES: Record<ConfidenceLevel, string> = {
  Strong: "border-transparent bg-emerald-600 text-white dark:bg-emerald-500",
  Moderate: "border-transparent bg-amber-500 text-white dark:bg-amber-500",
  Weak: "border-transparent bg-muted text-muted-foreground",
};

export function ConfidenceBadge({ confidence, className }: { confidence: ConfidenceLevel; className?: string }) {
  return (
    <Badge className={cn(STYLES[confidence], className)} title="Confidence reflects how directly the evidence was stated - not how large the opportunity is.">
      {confidence} confidence
    </Badge>
  );
}
