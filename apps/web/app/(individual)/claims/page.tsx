"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Scale } from "lucide-react";
import { api, unwrap } from "@/lib/api/client";
import { fullDateTime, timeAgo } from "@/lib/labels";
import { ClaimStatusBadge } from "@/components/claims/claim-status-badge";
import { ErrorState, LoadingState } from "@/components/states";
import { EmptyState, PageHeader } from "@/components/page";
import { Button } from "@/components/ui/button";

export default function MyClaimsPage() {
  const claims = useQuery({
    queryKey: ["claims", "mine"],
    queryFn: () => unwrap(api.GET("/api/v1/claims/mine", { params: { query: { limit: 50 } } })),
  });

  return (
    <div className="grid gap-6">
      <PageHeader title="My claims" description="Claims you've made on possible matches, and what happens next." />
      {claims.isPending ? (
        <LoadingState label="Loading claims…" />
      ) : claims.error ? (
        <ErrorState onRetry={() => claims.refetch()} retrying={claims.isFetching} />
      ) : !claims.data.length ? (
        <EmptyState
          icon={Scale}
          title="No claims yet"
          action={
            <Button asChild variant="outline">
              <Link href="/matches">View possible matches</Link>
            </Button>
          }
        >
          When a possible match looks like yours, you can claim it from its match page.
        </EmptyState>
      ) : (
        <ul className="divide-y surface">
          {claims.data.map((c) => (
            <li key={c.id}>
              <Link href={`/claims/${c.id}`} className="flex items-center gap-4 p-4 transition-colors hover:bg-muted/60 md:px-5">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{c.item_label}</span>
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
