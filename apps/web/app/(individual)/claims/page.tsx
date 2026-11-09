"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { api, unwrap } from "@/lib/api/client";
import { fullDateTime, timeAgo } from "@/lib/labels";
import { ClaimStatusBadge } from "@/components/claims/claim-status-badge";
import { ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";

export default function MyClaimsPage() {
  const claims = useQuery({
    queryKey: ["claims", "mine"],
    queryFn: () => unwrap(api.GET("/api/v1/claims/mine", { params: { query: { limit: 50 } } })),
  });

  return (
    <div className="grid gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">My claims</h1>
      {claims.isPending ? (
        <LoadingState label="Loading claims…" />
      ) : claims.error ? (
        <ErrorState onRetry={() => claims.refetch()} retrying={claims.isFetching} />
      ) : !claims.data.length ? (
        <div className="rounded-lg border bg-card p-8 text-center">
          <h2 className="font-semibold">No claims yet</h2>
          <p className="mt-1 text-muted-foreground">When a possible match looks like yours, you can claim it from its match page.</p>
          <Button asChild variant="outline" className="mt-4">
            <Link href="/matches">View possible matches</Link>
          </Button>
        </div>
      ) : (
        <ul className="divide-y rounded-lg border bg-card">
          {claims.data.map((c) => (
            <li key={c.id}>
              <Link href={`/claims/${c.id}`} className="flex items-center gap-4 p-4 hover:bg-muted/50 focus-visible:bg-muted/50">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{c.item_label}</span>
                    <ClaimStatusBadge status={c.status} />
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {c.reference}
                    {c.location_name && ` · ${c.location_name}`} ·{" "}
                    <time dateTime={c.created_at} title={fullDateTime(c.created_at)}>
                      {timeAgo(c.created_at)}
                    </time>
                  </p>
                </div>
                <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
