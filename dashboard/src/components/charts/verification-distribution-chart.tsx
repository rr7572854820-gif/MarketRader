"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { OpportunityEntry } from "@/lib/api/types";
import { EmptyChartState } from "@/components/charts/empty-chart-state";
import { hasOpportunities, topN, truncateLabel } from "@/components/charts/chart-utils";

/** The API does not expose a claim-level Verified/Partial/Unverified
 * breakdown for a report (only project_health.verification_percentage,
 * a single aggregate number, and each opportunity's own
 * verification_rate). So "distribution" here means what's honestly
 * available: how independently-verified each opportunity is, side by
 * side - not a fabricated claim-count breakdown the API never returns.
 */
export function VerificationDistributionChart({ opportunities }: { opportunities: OpportunityEntry[] }) {
  if (!hasOpportunities(opportunities)) {
    return <EmptyChartState message="No opportunities to chart yet." />;
  }

  const data = topN(
    [...opportunities].sort((a, b) => b.verification_rate - a.verification_rate),
    8
  ).map((o) => ({
    name: truncateLabel(o.title),
    fullName: o.title,
    rate: o.has_verification_data ? Math.round(o.verification_rate * 100) : 0,
    hasData: o.has_verification_data,
  }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border)" />
        <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} />
        <YAxis
          type="category"
          dataKey="name"
          width={140}
          tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
        />
        <Tooltip
          cursor={{ fill: "var(--accent)" }}
          contentStyle={{ background: "var(--popover)", color: "var(--popover-foreground)", border: "1px solid var(--border)", borderRadius: 8 }}
          formatter={(value, _name, item) => [
            (item.payload as { hasData: boolean }).hasData ? `${value}% verified` : "No verification data",
            "Verification rate",
          ]}
          labelFormatter={(_, payload) => payload?.[0]?.payload?.fullName ?? ""}
        />
        <Bar dataKey="rate" fill="var(--chart-2)" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
