"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/lib/api/client";
import { MatchCard, OWNERSHIP_WARNING } from "@/components/matches/match-card";
import { ErrorState, LoadingState } from "@/components/states";
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
      <div className="grid gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">{reportId ? "Possible matches for your report" : "Possible matches"}</h1>
        <p className="text-muted-foreground">{OWNERSHIP_WARNING} You&apos;ll prove ownership privately if you make a claim.</p>
        {reportId && (
          <Link href="/matches" className="text-sm text-primary underline-offset-4 hover:underline">
            Show matches for all your reports
          </Link>
        )}
      </div>
      {matches.isPending ? (
        <LoadingState label="Loading matches…" />
      ) : matches.error ? (
        <ErrorState onRetry={() => matches.refetch()} retrying={matches.isFetching} />
      ) : !items.length ? (
        <div className="rounded-lg border bg-card p-8 text-center">
          <h2 className="font-semibold">No possible matches yet</h2>
          <p className="mx-auto mt-1 max-w-md text-muted-foreground">
            We keep checking new found items across participating locations and will notify you if one may be yours.
          </p>
          <Button asChild variant="outline" className="mt-4">
            <Link href="/report/lost">Report something lost</Link>
          </Button>
        </div>
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
