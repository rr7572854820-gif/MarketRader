"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { OpportunityEntry } from "@/lib/api/types";
import { EmptyChartState } from "@/components/charts/empty-chart-state";
import { hasOpportunities, topN, truncateLabel } from "@/components/charts/chart-utils";

/** "Pain points" = opportunity clusters ranked by how many independent
 * discussions reported them (frequency/occurrence_count) - the most
 * directly evidence-backed number MarketRadar produces per opportunity,
 * deliberately charted here rather than the (SPECULATIVE)
 * opportunity_score, which gets its own separate chart.
 */
export function TopPainPointsChart({ opportunities }: { opportunities: OpportunityEntry[] }) {
  if (!hasOpportunities(opportunities)) {
    return <EmptyChartState message="No opportunities to chart yet." />;
  }

  const data = topN(
    [...opportunities].sort((a, b) => b.frequency - a.frequency),
    8
  ).map((o) => ({ name: truncateLabel(o.title), fullName: o.title, frequency: o.frequency }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border)" />
        <XAxis type="number" allowDecimals={false} tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} />
        <YAxis
          type="category"
          dataKey="name"
          width={140}
          tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
        />
        <Tooltip
          cursor={{ fill: "var(--accent)" }}
          contentStyle={{ background: "var(--popover)", color: "var(--popover-foreground)", border: "1px solid var(--border)", borderRadius: 8 }}
          formatter={(value) => [`${value} discussion(s)`, "Frequency"]}
          labelFormatter={(_, payload) => payload?.[0]?.payload?.fullName ?? ""}
        />
        <Bar dataKey="frequency" fill="var(--chart-1)" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
