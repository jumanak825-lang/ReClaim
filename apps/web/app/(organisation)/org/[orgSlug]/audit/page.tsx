"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { api, ApiError, unwrap } from "@/lib/api/client";
import { fullDateTime, humanizeKey } from "@/lib/labels";
import { useOrg } from "@/components/organisation/org-shell";
import { ErrorState, LoadingState, PermissionDenied } from "@/components/states";
import { PageHeader } from "@/components/page";
import { Button } from "@/components/ui/button";

// Audit log (docs/08 §8.9): append-only business events for this organisation.
export default function AuditLogPage() {
  const org = useOrg();
  const logs = useInfiniteQuery({
    queryKey: ["org", org.organisation_id, "audit"],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) => {
      const res = await api.GET("/api/v1/organisations/{org_id}/audit-logs", {
        params: { path: { org_id: org.organisation_id }, query: { limit: 50, ...(pageParam ? { cursor: pageParam } : {}) } },
      });
      const items = await unwrap(Promise.resolve(res));
      return { items, next: res.data?.meta.next_cursor ?? undefined };
    },
    getNextPageParam: (last) => last.next,
  });
  const items = logs.data?.pages.flatMap((p) => p.items) ?? [];

  if (logs.error instanceof ApiError && logs.error.status === 403) {
    return <PermissionDenied message="Only reviewers and managers can read the audit log." />;
  }
  return (
    <div className="grid gap-6">
      <PageHeader title="Audit log" description="Claim decisions, custody changes, recoveries and payments, newest first." />
      {logs.isPending ? (
        <LoadingState label="Loading audit log…" />
      ) : logs.error ? (
        <ErrorState onRetry={() => logs.refetch()} retrying={logs.isFetching} />
      ) : !items.length ? (
        <p className="surface p-8 text-center text-muted-foreground">No audit events yet.</p>
      ) : (
        <>
          <div className="overflow-x-auto surface">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="bg-muted text-left text-muted-foreground">
                <tr>
                  <th scope="col" className="p-3 font-medium">When</th>
                  <th scope="col" className="p-3 font-medium">Who</th>
                  <th scope="col" className="p-3 font-medium">Action</th>
                  <th scope="col" className="p-3 font-medium">Record</th>
                  <th scope="col" className="p-3 font-medium">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {items.map((a) => (
                  <tr key={a.id}>
                    <td className="p-3 whitespace-nowrap">{fullDateTime(a.created_at)}</td>
                    <td className="p-3">{a.actor_display_name ?? "System"}</td>
                    <td className="p-3 font-mono text-xs">{a.action}</td>
                    <td className="p-3">
                      {humanizeKey(a.entity_type)} <span className="font-mono text-xs text-muted-foreground">{a.entity_id.slice(0, 8)}</span>
                    </td>
                    <td className="p-3">{a.reason ?? <span className="text-muted-foreground">None</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {logs.hasNextPage && (
            <Button variant="outline" className="justify-self-center" onClick={() => logs.fetchNextPage()} disabled={logs.isFetchingNextPage}>
              {logs.isFetchingNextPage ? "Loading…" : "Load more"}
            </Button>
          )}
        </>
      )}
    </div>
  );
}
