"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ClipboardList, PackageCheck, PackageSearch, Search, Scale } from "lucide-react";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { useMe } from "@/lib/api/me";
import { ActivityList } from "@/components/activity-list";
import { StatCard } from "@/components/stat-card";
import { ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";

// Screen 3 (docs/02 §2.4): the user's own reports, matches, claims and recoveries only.
export default function DashboardPage() {
  const { data: me } = useMe();
  const dashboard = useQuery({
    queryKey: ["me", "dashboard"],
    queryFn: () => unwrap(api.GET("/api/v1/me/dashboard")),
  });

  return (
    <div className="grid gap-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Welcome, {me?.display_name}</h1>
          <p className="text-muted-foreground">Your reports, matches and recoveries.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild>
            <Link href="/report/lost">
              <PackageSearch aria-hidden /> Report lost
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/report/found">
              <ClipboardList aria-hidden /> Report found
            </Link>
          </Button>
        </div>
      </div>

      {dashboard.isPending ? (
        <LoadingState label="Loading your dashboard…" />
      ) : dashboard.error ? (
        <ErrorState onRetry={() => dashboard.refetch()} retrying={dashboard.isFetching} />
      ) : (
        <DashboardBody data={dashboard.data} />
      )}
    </div>
  );
}

function DashboardBody({ data }: { data: Schemas["DashboardOut"] }) {
  const c = data.counts;
  const isNew =
    !data.recent_activity.length &&
    c.active_lost_reports + c.active_found_reports + c.potential_matches + c.claims_awaiting_review + c.active_recoveries === 0;

  if (isNew) {
    return (
      <section className="rounded-lg border bg-card p-8 text-center">
        <h2 className="text-lg font-semibold">Start with your first report</h2>
        <p className="mx-auto mt-2 max-w-md text-muted-foreground">
          Lost something? Describe it once, with where and when you last had it. We&apos;ll look for possible matches
          across participating locations and let you know. Found something? Report it so its owner can find it.
        </p>
      </section>
    );
  }

  return (
    <>
      <section aria-labelledby="summary-heading">
        <h2 id="summary-heading" className="sr-only">
          Summary
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Active lost reports" value={c.active_lost_reports} icon={PackageSearch} />
          <StatCard
            label="Potential matches"
            value={c.potential_matches}
            icon={Search}
            note="Possible matches, not confirmed ownership"
          />
          <StatCard label="Claims awaiting review" value={c.claims_awaiting_review} icon={Scale} />
          <StatCard label="Active recoveries" value={c.active_recoveries} icon={PackageCheck} />
        </div>
      </section>

      <section aria-labelledby="activity-heading" className="grid gap-3">
        <h2 id="activity-heading" className="text-lg font-semibold">
          Recent activity
        </h2>
        <ActivityList items={data.recent_activity} empty="Nothing new yet. Updates on your reports will appear here." />
      </section>
    </>
  );
}

