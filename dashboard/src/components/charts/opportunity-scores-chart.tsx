"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { OpportunityEntry } from "@/lib/api/types";
import { EmptyChartState } from "@/components/charts/empty-chart-state";
import { hasOpportunities, topN, truncateLabel } from "@/components/charts/chart-utils";

/** opportunity_score is explicitly SPECULATIVE (AI-inferred, not a
 * verified finding - see src/insights/models.py in the backend). This
 * chart exists to help compare opportunities at a glance, not to
 * present the score as a validated ranking - the axis label and
 * tooltip both say so rather than letting the number speak alone.
 */
export function OpportunityScoresChart({ opportunities }: { opportunities: OpportunityEntry[] }) {
  if (!hasOpportunities(opportunities)) {
    return <EmptyChartState message="No opportunities to chart yet." />;
  }

  const data = topN(
    [...opportunities].sort((a, b) => b.opportunity_score - a.opportunity_score),
    8
  ).map((o) => ({ name: truncateLabel(o.title), fullName: o.title, score: o.opportunity_score }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border)" />
        <XAxis type="number" domain={[0, 100]} tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} />
        <YAxis
          type="category"
          dataKey="name"
          width={140}
          tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
        />
        <Tooltip
          cursor={{ fill: "var(--accent)" }}
          contentStyle={{ background: "var(--popover)", color: "var(--popover-foreground)", border: "1px solid var(--border)", borderRadius: 8 }}
          formatter={(value) => [`${value} / 100 (SPECULATIVE)`, "Opportunity score"]}
          labelFormatter={(_, payload) => payload?.[0]?.payload?.fullName ?? ""}
        />
        <Bar dataKey="score" fill="var(--chart-3)" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
