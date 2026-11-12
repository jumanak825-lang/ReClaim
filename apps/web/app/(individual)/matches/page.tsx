"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/lib/api/client";
import { MatchCard, OWNERSHIP_WARNING } from "@/components/matches/match-card";
import { Search } from "lucide-react";
import { ErrorState, LoadingState } from "@/components/states";
import { EmptyState, PageHeader } from "@/components/page";
import { Button } from "@/components/ui/button";

// Screen 7 (docs/02 §2.4). ?report=<id> narrows to one lost report's candidates.
export default function MatchesPage() {
  const reportId = useSearchParams().get("report");
  const matches = useQuery({
    queryKey: ["matches", reportId ?? "mine"],
    queryFn: () =>
      reportId
        ? unwrap(api.GET("/api/v1/reports/{report_id}/matches", { params: { path: { report_id: reportId }, query: { limit: 50 } } }))
        : unwrap(api.GET("/api/v1/matches/mine", { params: { query: { limit: 50 } } })),
  });
  // Owners see candidates for their lost reports; dismissed ones drop out of this list.
  const items = (matches.data ?? []).filter((m) => m.status !== "dismissed");

  return (
    <div className="grid gap-6">
      <PageHeader
        title={reportId ? "Possible matches for your report" : "Possible matches"}
        description={<>{OWNERSHIP_WARNING} You&apos;ll prove ownership privately if you make a claim.</>}
        actions={
          reportId && (
            <Link href="/matches" className="text-sm font-medium text-brand underline-offset-4 hover:underline">
              Show matches for all your reports
            </Link>
          )
        }
      />
      {matches.isPending ? (
        <LoadingState label="Loading matches…" />
      ) : matches.error ? (
        <ErrorState onRetry={() => matches.refetch()} retrying={matches.isFetching} />
      ) : !items.length ? (
        <EmptyState
          icon={Search}
          title="No possible matches yet"
          action={
            <Button asChild variant="outline">
              <Link href="/report/lost">Report something lost</Link>
            </Button>
          }
        >
          We keep checking new found items across participating locations and will notify you if one may be yours.
        </EmptyState>
      ) : (
        <ul className="grid gap-3">
          {items.map((m) => (
            <MatchCard key={m.id} match={m} />
          ))}
        </ul>
      )}
    </div>
  );
}
