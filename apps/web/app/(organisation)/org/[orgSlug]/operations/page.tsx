"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { api, unwrap } from "@/lib/api/client";
import { claimStatusLabel, priorityLabel, reportStatusLabel } from "@/lib/labels";
import { useOrg } from "@/components/organisation/org-shell";
import { ALL_LOCATIONS, LocationSelect } from "@/components/organisation/location-select";
import { CasesGrid, type CaseRow } from "@/components/organisation/cases-grid";
import { ErrorState, LoadingState } from "@/components/states";
import { PageHeader } from "@/components/page";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const MAX_ROWS = 500;

// Screen 11 (docs/02 §2.4). Rows come from the API already scoped to this user's org and locations.
export default function OperationsPage() {
  const org = useOrg();
  const [quick, setQuick] = useState("");
  const [locationId, setLocationId] = useState(ALL_LOCATIONS);

  const locations = useQuery({
    queryKey: ["org", org.organisation_id, "locations"],
    queryFn: () => unwrap(api.GET("/api/v1/organisations/{org_id}/locations", { params: { path: { org_id: org.organisation_id } } })),
  });
  const visible = (locations.data ?? []).filter((l) => !org.location_ids.length || org.location_ids.includes(l.id));

  const cases = useQuery({
    queryKey: ["org", org.organisation_id, "cases", "all", locationId],
    queryFn: async () => {
      // Follow the cursor until the end (bounded) so the grid can sort and filter everything in scope.
      const rows: CaseRow[] = [];
      let cursor: string | undefined;
      do {
        const res = await api.GET("/api/v1/organisations/{org_id}/cases", {
          params: {
            path: { org_id: org.organisation_id },
            query: { limit: 100, ...(cursor ? { cursor } : {}), ...(locationId !== ALL_LOCATIONS ? { location_id: locationId } : {}) },
          },
        });
        rows.push(...(await unwrap(Promise.resolve(res))));
        cursor = res.data?.meta.next_cursor ?? undefined;
      } while (cursor && rows.length < MAX_ROWS);
      return { rows, truncated: !!cursor };
    },
  });

  return (
    <div className="grid gap-5">
      <PageHeader
        title="Operations"
        description="Found items your organisation holds, with matches, claims and recoveries."
        actions={
          visible.length > 0 && (
            <LocationSelect
              locations={visible}
              value={locationId}
              onChange={setLocationId}
              allLabel={org.location_ids.length ? "All my locations" : "All locations"}
            />
          )
        }
      />

      <div className="grid max-w-sm gap-1.5">
        <Label htmlFor="quick-search">Quick search</Label>
        <div className="relative">
          <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input id="quick-search" className="pl-9" placeholder="Item, case ID, location…" value={quick} onChange={(e) => setQuick(e.target.value)} />
        </div>
      </div>

      {cases.isPending ? (
        <LoadingState label="Loading cases…" />
      ) : cases.error ? (
        <ErrorState onRetry={() => cases.refetch()} retrying={cases.isFetching} />
      ) : (
        <>
          {cases.data.truncated && (
            <p className="text-sm text-muted-foreground">Showing the first {MAX_ROWS} cases. Narrow by location to see the rest.</p>
          )}
          {/* Desktop: AG Grid. Narrow screens: card rows (docs/02 §2.6). */}
          <div className="hidden md:block">
            <CasesGrid rows={cases.data.rows} quickFilter={quick} orgSlug={org.organisation_slug} />
          </div>
          <CaseCards rows={cases.data.rows} quick={quick} orgSlug={org.organisation_slug} />
        </>
      )}
    </div>
  );
}

function CaseCards({ rows, quick, orgSlug }: { rows: CaseRow[]; quick: string; orgSlug: string }) {
  const q = quick.trim().toLowerCase();
  const shown = q
    ? rows.filter((r) => [r.item_label, r.case_reference, r.location_name ?? ""].some((v) => v.toLowerCase().includes(q)))
    : rows;
  return (
    <ul className="grid gap-2 md:hidden" aria-label="Cases">
      {shown.length === 0 && <li className="surface p-4 text-muted-foreground">No cases match.</li>}
      {shown.map((r) => (
        <li key={r.id}>
          <Link href={`/org/${orgSlug}/cases/${r.id}`} className="grid gap-1 surface p-4 transition-colors hover:border-foreground/40">
            <span className="font-medium">
              {r.item_label} <span className="font-normal text-muted-foreground">· {r.case_reference}</span>
            </span>
            <span className="text-sm text-muted-foreground">
              {[
                r.location_name,
                reportStatusLabel[r.report_status],
                r.claim_status && `Claim: ${claimStatusLabel[r.claim_status]}`,
                priorityLabel[r.priority],
              ]
                .filter(Boolean)
                .join(" · ")}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
