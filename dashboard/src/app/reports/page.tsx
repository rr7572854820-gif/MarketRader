"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowUpDown, Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ErrorState } from "@/components/error-state";
import { ReportsTableSkeleton } from "@/components/skeletons/reports-table-skeleton";
import { api } from "@/lib/api/client";
import type { ReportListItem } from "@/lib/api/types";

type SortOrder = "newest" | "oldest";

function formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function ReportsPage() {
  const [reports, setReports] = React.useState<ReportListItem[] | null>(null);
  const [error, setError] = React.useState<unknown>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [search, setSearch] = React.useState("");
  const [sortOrder, setSortOrder] = React.useState<SortOrder>("newest");

  // Split in two so the mount effect never calls setState synchronously
  // (only fetchReports, whose setState calls happen inside async
  // .then/.catch/.finally callbacks): isLoading/error already start at
  // the right "loading, no error" values via useState above, so the
  // effect doesn't need to re-set them. retry() is different - it runs
  // from a button's onClick, a real event handler, where a synchronous
  // setState is completely normal and not subject to this rule.
  const fetchReports = React.useCallback(() => {
    api
      .listReports(100)
      .then(setReports)
      .catch(setError)
      .finally(() => setIsLoading(false));
  }, []);

  const retry = React.useCallback(() => {
    setIsLoading(true);
    setError(null);
    fetchReports();
  }, [fetchReports]);

  React.useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  const visibleReports = React.useMemo(() => {
    if (!reports) return [];
    const filtered = search.trim()
      ? reports.filter((r) => r.report_id.toLowerCase().includes(search.trim().toLowerCase()))
      : reports;
    const sorted = [...filtered].sort((a, b) => {
      const diff = new Date(a.start_time).getTime() - new Date(b.start_time).getTime();
      return sortOrder === "newest" ? -diff : diff;
    });
    return sorted;
  }, [reports, search, sortOrder]);

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Reports</h1>
        <p className="text-muted-foreground">Every run recorded by the API&apos;s output directory - CLI and dashboard runs together.</p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by report ID…"
            className="pl-8"
            aria-label="Search reports by ID"
          />
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setSortOrder((o) => (o === "newest" ? "oldest" : "newest"))}
        >
          <ArrowUpDown className="size-4" />
          {sortOrder === "newest" ? "Newest first" : "Oldest first"}
        </Button>
      </div>

      {isLoading ? <ReportsTableSkeleton /> : null}

      {!isLoading && error ? <ErrorState error={error} onRetry={retry} /> : null}

      {!isLoading && !error && reports && reports.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            No reports yet. Run an analysis from the Home page to create one.
          </CardContent>
        </Card>
      ) : null}

      {!isLoading && !error && reports && reports.length > 0 ? (
        <>
          {visibleReports.length === 0 ? (
            <p className="text-sm text-muted-foreground">No reports match &ldquo;{search}&rdquo;.</p>
          ) : (
            <div className="overflow-x-auto rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Report ID</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Fetched</TableHead>
                    <TableHead className="text-right">Analyzed</TableHead>
                    <TableHead className="text-right">Clusters</TableHead>
                    <TableHead className="sr-only">View</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleReports.map((report) => (
                    <TableRow key={report.report_id}>
                      <TableCell className="font-mono text-xs">{report.report_id}</TableCell>
                      <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                        {formatTimestamp(report.start_time)}
                      </TableCell>
                      <TableCell>
                        <Badge variant={report.succeeded ? "secondary" : "destructive"}>
                          {report.succeeded ? "Succeeded" : "Failed"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">{report.posts_fetched}</TableCell>
                      <TableCell className="text-right">{report.posts_analyzed}</TableCell>
                      <TableCell className="text-right">{report.clusters_found}</TableCell>
                      <TableCell>
                        <Button render={<Link href={`/reports/${report.report_id}`} />} nativeButton={false} variant="outline" size="sm">
                          View
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
