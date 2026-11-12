"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Scale } from "lucide-react";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { categoryLabel, fullDateTime, timeAgo } from "@/lib/labels";
import { ClaimStatusBadge } from "@/components/claims/claim-status-badge";
import { useOrg } from "@/components/organisation/org-shell";
import { ErrorState, LoadingState } from "@/components/states";
import { EmptyState, PageHeader, SegmentedControl } from "@/components/page";

type Tab = "pending" | "escalated" | "decided";
const tabs: { value: Tab; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "escalated", label: "Escalated" },
  { value: "decided", label: "Decided" },
];

// Screen 9 (docs/02 §2.4): queue grouped by pending, escalated, decided.
export default function ClaimQueuePage() {
  const org = useOrg();
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const raw = searchParams.get("tab");
  const tab: Tab = raw === "escalated" || raw === "decided" ? raw : "pending";

  const statuses: Schemas["ClaimListItem"]["status"][] = tab === "decided" ? ["approved", "rejected"] : [tab];
  const claims = useQuery({
    queryKey: ["org", org.organisation_id, "claims", tab],
    queryFn: async () => {
      const lists = await Promise.all(
        statuses.map((status) =>
          unwrap(
            api.GET("/api/v1/organisations/{org_id}/claims", {
              params: { path: { org_id: org.organisation_id }, query: { status, limit: 100 } },
            }),
          ),
        ),
      );
      return lists.flat().sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    },
  });

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Claims"
        description={
          org.role === "staff" ? "You can follow claims; reviewers decide them." : "Review ownership claims for items your organisation holds."
        }
      />
      <SegmentedControl
        label="Claim status"
        options={tabs}
        value={tab}
        onChange={(v) => router.replace(v === "pending" ? pathname : `${pathname}?tab=${v}`, { scroll: false })}
      />
      {claims.isPending ? (
        <LoadingState label="Loading claims…" />
      ) : claims.error ? (
        <ErrorState onRetry={() => claims.refetch()} retrying={claims.isFetching} />
      ) : !claims.data.length ? (
        <EmptyState icon={Scale} title={`No ${tab} claims`}>
          {tab === "pending" ? "New claims on items your organisation holds will appear here." : "Nothing here right now."}
        </EmptyState>
      ) : (
        <ul className="divide-y surface">
          {claims.data.map((c) => (
            <li key={c.id}>
              <Link
                href={`/org/${org.organisation_slug}/claims/${c.id}`}
                className="flex items-center gap-4 p-4 transition-colors hover:bg-muted/60 md:px-5"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{c.item_label}</span>
                    <ClaimStatusBadge status={c.status} />
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {c.reference} · {categoryLabel[c.category]}
                    {c.location_name && ` · ${c.location_name}`}
                    {c.claimant_display_name && ` · ${c.claimant_display_name}`} · AI relevance {Math.round(c.score)} ·{" "}
                    <time dateTime={c.updated_at} title={fullDateTime(c.updated_at)}>
                      {timeAgo(c.updated_at)}
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
