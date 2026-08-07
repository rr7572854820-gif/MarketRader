import { Check, X } from "lucide-react";

import { cn } from "@/lib/utils";

const CHATGPT_ITEMS = [
  "Generates plausible-sounding answers",
  "No real sources cited",
  "Cannot verify claims",
  "Data from training cutoff",
  "No trend tracking",
  "Forgets everything tomorrow",
];

const MARKETRADAR_ITEMS = [
  "Real discussions from real people",
  "Every quote verified against source",
  "GitHub Issues + Hacker News data",
  "Updated in real-time",
  "Historical trend tracking",
  "Persistent research history",
];

function ComparisonList({
  items,
  positive,
}: {
  items: string[];
  positive: boolean;
}) {
  const Icon = positive ? Check : X;
  return (
    <ul className="mt-6 space-y-3">
      {items.map((item) => (
        <li key={item} className="flex items-start gap-2.5 text-sm">
          <Icon
            className={cn("mt-0.5 size-4 shrink-0", positive ? "text-emerald-500" : "text-muted-foreground")}
            aria-hidden="true"
          />
          <span className={positive ? "text-foreground" : "text-muted-foreground"}>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function ComparisonSection() {
  return (
    <section className="mx-auto max-w-4xl px-4 py-20 sm:py-28">
      <h2 className="text-balance text-center text-3xl font-semibold tracking-tight sm:text-4xl">
        Why not just ask ChatGPT?
      </h2>
      <div className="mt-14 grid gap-6 sm:grid-cols-2">
        <div className="rounded-xl border border-white/10 p-6">
          <h3 className="text-sm font-medium text-muted-foreground">AI Assistants</h3>
          <ComparisonList items={CHATGPT_ITEMS} positive={false} />
        </div>
        <div className="rounded-xl border-2 border-foreground/20 bg-card p-6 shadow-lg">
          <h3 className="text-sm font-medium">MarketRadar</h3>
          <ComparisonList items={MARKETRADAR_ITEMS} positive={true} />
        </div>
      </div>
    </section>
  );
}
