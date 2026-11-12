"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Archive, ClipboardPlus, FolderOpen, PackageCheck, Scale } from "lucide-react";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { claimStatusLabel, fullDateTime, priorityLabel, recoveryStatusLabel, timeAgo } from "@/lib/labels";
import { useOrg } from "@/components/organisation/org-shell";
import { ALL_LOCATIONS, LocationSelect } from "@/components/organisation/location-select";
import { ActivityList } from "@/components/activity-list";
import { StatCard } from "@/components/stat-card";
import { ErrorState, LoadingState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

// Screen 10 (docs/02 §2.4).
export default function OrganisationOverviewPage() {
  const org = useOrg();
  const orgId = org.organisation_id;
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const locations = useQuery({
    queryKey: ["org", orgId, "locations"],
    queryFn: () => unwrap(api.GET("/api/v1/organisations/{org_id}/locations", { params: { path: { org_id: orgId } } })),
  });
  // Staff assigned to specific locations only see those; no assignment means all locations.
  const visible = (locations.data ?? []).filter((l) => !org.location_ids.length || org.location_ids.includes(l.id));
  const requested = searchParams.get("location");
  const locationId = visible.some((l) => l.id === requested) ? requested! : null;

  const setLocation = (value: string) => {
    const params = new URLSearchParams(searchParams);
    if (value === ALL_LOCATIONS) params.delete("location");
    else params.set("location", value);
    router.replace(params.size ? `${pathname}?${params}` : pathname, { scroll: false });
  };

  const overview = useQuery({
    queryKey: ["org", orgId, "overview", { locationId }],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/organisations/{org_id}/overview", {
          params: { path: { org_id: orgId }, query: locationId ? { location_id: locationId } : {} },
        }),
      ),
  });
  const scopeLabel = locationId
    ? `At ${visible.find((l) => l.id === locationId)?.name}`
    : org.location_ids.length
      ? "Across all your locations"
      : "Across all locations";

  return (
    <div className="grid gap-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{org.organisation_name}</h1>
          <p className="text-muted-foreground">
            Overview · signed in as <span className="capitalize">{org.role}</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {visible.length > 0 && (
            <LocationSelect
              locations={visible}
              value={locationId ?? ALL_LOCATIONS}
              onChange={setLocation}
              allLabel={org.location_ids.length ? "All my locations" : "All locations"}
            />
          )}
          <Button asChild>
            <Link href={`/report/found?org=${org.organisation_slug}`}>
              <ClipboardPlus aria-hidden /> Log found item
            </Link>
          </Button>
        </div>
      </div>

      {overview.isPending ? (
        <LoadingState label="Loading overview…" />
      ) : overview.error ? (
        <ErrorState onRetry={() => overview.refetch()} retrying={overview.isFetching} />
      ) : (
        <OverviewCards data={overview.data} scopeLabel={scopeLabel} />
      )}

      <PriorityQueue orgId={orgId} orgSlug={org.organisation_slug} locationId={locationId} />

      {overview.data && (
        <section aria-labelledby="activity-heading" className="grid gap-3">
          <h2 id="activity-heading" className="text-lg font-semibold">
            Recent activity
          </h2>
          <ActivityList items={overview.data.recent_activity} empty="No recent activity." />
        </section>
      )}
    </div>
  );
}

function OverviewCards({ data, scopeLabel }: { data: Schemas["OrgOverviewOut"]; scopeLabel: string }) {
  return (
    <section aria-labelledby="summary-heading" className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="summary-heading" className="text-lg font-semibold">
          Summary
        </h2>
        <span className="text-sm text-muted-foreground">{scopeLabel}</span>
        {data.is_seeded_demo_data && <Badge variant="outline">Seeded demo data</Badge>}
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Active cases" value={data.active_cases} icon={FolderOpen} />
        <StatCard label="Found inventory" value={data.found_inventory} icon={Archive} note="Items your organisation holds" />
        <StatCard
          label="Pending claims"
          value={data.pending_claims}
          icon={Scale}
          note={data.escalated_claims ? `Plus ${data.escalated_claims} escalated` : undefined}
        />
        <StatCard label="Recoveries in progress" value={data.recoveries_in_progress} icon={PackageCheck} />
      </div>
    </section>
  );
}

function PriorityQueue({ orgId, orgSlug, locationId }: { orgId: string; orgSlug: string; locationId: string | null }) {
  const cases = useQuery({
    queryKey: ["org", orgId, "cases", { sort: "priority", limit: 5, locationId }],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/organisations/{org_id}/cases", {
          params: {
            path: { org_id: orgId },
            query: { sort: "priority", limit: 5, status: "active", ...(locationId ? { location_id: locationId } : {}) },
          },
        }),
      ),
  });

  return (
    <section aria-labelledby="queue-heading" className="grid gap-3">
      <h2 id="queue-heading" className="text-lg font-semibold">
        Priority queue
      </h2>
      {cases.isPending ? (
        <LoadingState label="Loading cases…" />
      ) : cases.error ? (
        <ErrorState onRetry={() => cases.refetch()} retrying={cases.isFetching} />
      ) : !cases.data.length ? (
        <p className="text-muted-foreground">No active cases{locationId ? " at this location" : ""}.</p>
      ) : (
        <ul className="divide-y rounded-lg border bg-card">
          {cases.data.map((c) => (
            <li key={c.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 p-4">
              <div className="min-w-0 flex-1">
                <Link href={`/org/${orgSlug}/cases/${c.id}`} className="font-medium underline-offset-4 hover:underline">
                  {c.item_label} <span className="font-normal text-muted-foreground">· {c.case_reference}</span>
                </Link>
                <p className="text-sm text-muted-foreground">
                  {[
                    c.location_name,
                    c.claim_status && `Claim: ${claimStatusLabel[c.claim_status]}`,
                    c.recovery_status && `Recovery: ${recoveryStatusLabel[c.recovery_status]}`,
                    !c.claim_status && c.candidate_match_id && "Candidate match",
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
              <PriorityBadge priority={c.priority} />
              <time dateTime={c.updated_at} title={fullDateTime(c.updated_at)} className="text-sm text-muted-foreground">
                Updated {timeAgo(c.updated_at)}
              </time>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function PriorityBadge({ priority }: { priority: Schemas["CaseRow"]["priority"] }) {
  // Text and icon carry the meaning, not colour alone (docs/02 §2.7).
  if (priority === "high") {
    return (
      <Badge className="bg-warning text-warning-foreground">
        <AlertTriangle aria-hidden /> {priorityLabel.high}
      </Badge>
    );
  }
  return <Badge variant={priority === "medium" ? "secondary" : "outline"}>{priorityLabel[priority]}</Badge>;
}
