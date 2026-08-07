import { AnalysisForm } from "@/components/analysis-form";

export default function DashboardHomePage() {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Run a new analysis</h1>
        <p className="text-muted-foreground">
          Evidence-backed market research, on demand - every result here comes straight from the MarketRadar
          pipeline through its REST API.
        </p>
      </div>
      <AnalysisForm />
    </div>
  );
}
