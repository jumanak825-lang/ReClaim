"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { EyeOff } from "lucide-react";
import { api, ApiError, unwrap } from "@/lib/api/client";
import { categoryLabel, custodyLabel, fullDateTime, humanizeKey, matchStatusLabel, recoveryStatusLabel } from "@/lib/labels";
import { ClaimStatusBadge } from "@/components/claims/claim-status-badge";
import { Relevance } from "@/components/matches/match-card";
import { useOrg } from "@/components/organisation/org-shell";
import { ReportStatusBadge } from "@/components/reports/report-status-badge";
import { ErrorState, LoadingState, PermissionDenied } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

// Case detail for staff: the found item (custodian view), its candidates, claims and recovery.
export default function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const org = useOrg();
  const slug = org.organisation_slug;
  const detail = useQuery({
    queryKey: ["org", org.organisation_id, "case", caseId],
    queryFn: () =>
      unwrap(api.GET("/api/v1/organisations/{org_id}/cases/{case_id}", { params: { path: { org_id: org.organisation_id, case_id: caseId } } })),
  });

  if (detail.isPending) return <LoadingState label="Loading case…" />;
  if (detail.error) {
    return detail.error instanceof ApiError && detail.error.status === 404 ? (
      <PermissionDenied
        message="We couldn't find this case in your organisation or locations."
        action={
          <Button asChild variant="outline">
            <Link href={`/org/${slug}/operations`}>Back to operations</Link>
          </Button>
        }
      />
    ) : (
      <ErrorState onRetry={() => detail.refetch()} retrying={detail.isFetching} />
    );
  }
  const { case_reference, found_report: r, matches, claims, recovery } = detail.data;

  return (
    <div className="mx-auto grid w-full max-w-4xl gap-6">
      <Link href={`/org/${slug}/operations`} className="text-sm text-primary underline-offset-4 hover:underline">
        ← Operations
      </Link>
      <div className="grid gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">Case {case_reference}</Badge>
          <ReportStatusBadge status={r.status} />
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">{r.item_label}</h1>
        <p className="text-sm text-muted-foreground">
          {r.location?.name ?? r.location_label} · found {r.found_at ? fullDateTime(r.found_at) : "time not given"}
          {r.custody_status && ` · ${custodyLabel[r.custody_status]}`}
        </p>
      </div>

      <section aria-labelledby="item-heading" className="grid gap-3 rounded-lg border bg-card p-5">
        <h2 id="item-heading" className="font-semibold">
          Item
        </h2>
        <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[10rem_1fr]">
          <dt className="text-muted-foreground">Category</dt>
          <dd>{categoryLabel[r.category]}</dd>
          <dt className="text-muted-foreground">Description</dt>
          <dd className="whitespace-pre-line">{r.description}</dd>
          {Object.entries(r.attributes_public).map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-muted-foreground">{humanizeKey(k)}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
        {(r.storage_reference || (r.attributes_private && Object.keys(r.attributes_private).length > 0)) && (
          <div className="grid gap-2 rounded-md border border-dashed p-3">
            <h3 className="flex items-center gap-1.5 text-sm font-medium">
              <EyeOff className="size-4" aria-hidden /> Private: your organisation only
            </h3>
            <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[10rem_1fr]">
              {r.storage_reference && (
                <>
                  <dt className="text-muted-foreground">Storage reference</dt>
                  <dd>{r.storage_reference}</dd>
                </>
              )}
              {Object.entries(r.attributes_private ?? {}).map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="text-muted-foreground">{humanizeKey(k)}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}
      </section>

      <section aria-labelledby="candidates-heading" className="grid gap-3">
        <h2 id="candidates-heading" className="font-semibold">
          Candidate matches
        </h2>
        {matches.length ? (
          <ul className="grid gap-2">
            {matches.map((m) => (
              <li key={m.id} className="grid gap-2 rounded-lg border bg-card p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">Lost report: {m.lost_item.item_label}</span>
                  <Badge variant="outline">{matchStatusLabel[m.status]}</Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  {m.lost_item.approximate_location} · {m.explanation.join(" · ")}
                </p>
                <Relevance match={m} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No candidate matches yet.</p>
        )}
      </section>

      <section aria-labelledby="claims-heading" className="grid gap-3">
        <h2 id="claims-heading" className="font-semibold">
          Claims
        </h2>
        {claims.length ? (
          <ul className="divide-y rounded-lg border bg-card">
            {claims.map((c) => (
              <li key={c.id}>
                <Link href={`/org/${slug}/claims/${c.id}`} className="flex flex-wrap items-center gap-2 p-4 hover:bg-muted/50">
                  <span className="font-medium">{c.reference}</span>
                  <ClaimStatusBadge status={c.status} />
                  {c.claimant_display_name && <span className="text-sm text-muted-foreground">{c.claimant_display_name}</span>}
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No claims yet.</p>
        )}
      </section>

      {recovery && (
        <section aria-labelledby="recovery-heading" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-card p-4">
          <div>
            <h2 id="recovery-heading" className="font-semibold">
              Recovery
            </h2>
            <p className="text-sm text-muted-foreground">
              {recovery.method === "collection" ? "Collection" : "Delivery"} · {recoveryStatusLabel[recovery.status]}
            </p>
          </div>
          <Button asChild size="sm">
            <Link href={`/org/${slug}/recoveries/${recovery.id}`}>Manage recovery</Link>
          </Button>
        </section>
      )}
    </div>
  );
}
