"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useInfiniteQuery } from "@tanstack/react-query";
import { ChevronRight, ClipboardList } from "lucide-react";
import { api, unwrap } from "@/lib/api/client";
import { categoryLabel, fullDateTime, timeAgo } from "@/lib/labels";
import { ReportStatusBadge } from "@/components/reports/report-status-badge";
import { wizardHref } from "@/components/reports/resume-report";
import { ErrorState, LoadingState } from "@/components/states";
import { EmptyState, PageHeader, SegmentedControl } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Filter = "all" | "lost" | "found";
const filters: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "lost", label: "Lost" },
  { value: "found", label: "Found" },
];

export default function MyReportsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const raw = searchParams.get("type");
  const filter: Filter = raw === "lost" || raw === "found" ? raw : "all";

  const reports = useInfiniteQuery({
    queryKey: ["reports", "mine", filter],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) => {
      const { data, error, response } = await api.GET("/api/v1/reports/mine", {
        params: { query: { limit: 20, ...(pageParam ? { cursor: pageParam } : {}), ...(filter !== "all" ? { type: filter } : {}) } },
      });
      // Keep next_cursor, which unwrap() drops.
      const items = await unwrap(Promise.resolve({ data, error, response }));
      return { items, next: data?.meta.next_cursor ?? undefined };
    },
    getNextPageParam: (last) => last.next,
  });

  const items = reports.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="grid gap-6">
      <PageHeader
        title="My reports"
        description="Everything you've reported lost or found, and where each one is."
        actions={
          <>
            <Button asChild>
              <Link href="/report/lost">Report lost</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/report/found">Report found</Link>
            </Button>
          </>
        }
      />

      <SegmentedControl
        label="Filter reports"
        options={filters}
        value={filter}
        onChange={(v) => router.replace(v === "all" ? pathname : `${pathname}?type=${v}`, { scroll: false })}
      />

      {reports.isPending ? (
        <LoadingState label="Loading your reports…" />
      ) : reports.error ? (
        <ErrorState onRetry={() => reports.refetch()} retrying={reports.isFetching} />
      ) : !items.length ? (
        <EmptyState icon={ClipboardList} title={`No ${filter === "all" ? "" : `${filter} `}reports yet`}>
          Reports you create will appear here so you can follow them.
        </EmptyState>
      ) : (
        <>
          <ul className="divide-y surface">
            {items.map((r) => {
              const href = r.status === "draft" ? wizardHref(r) : `/reports/${r.id}`;
              return (
                <li key={r.id}>
                  <Link href={href} className="flex items-center gap-4 p-4 transition-colors hover:bg-muted/60 md:px-5">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold">{r.item_label}</span>
                        <Badge variant="outline">{r.report_type === "lost" ? "Lost" : "Found"}</Badge>
                        <ReportStatusBadge status={r.status} />
                      </div>
                      <p className="mt-1 truncate text-sm text-muted-foreground">
                        {categoryLabel[r.category]} · {r.location_label} ·{" "}
                        <time dateTime={r.created_at} title={fullDateTime(r.created_at)}>
                          {timeAgo(r.created_at)}
                        </time>
                        {r.status === "draft" && " · Continue where you left off"}
                      </p>
                    </div>
                    <ChevronRight className={cn("size-4 shrink-0 text-muted-foreground")} aria-hidden />
                  </Link>
                </li>
              );
            })}
          </ul>
          {reports.hasNextPage && (
            <Button variant="outline" className="justify-self-center" onClick={() => reports.fetchNextPage()} disabled={reports.isFetchingNextPage}>
              {reports.isFetchingNextPage ? "Loading…" : "Load more"}
            </Button>
          )}
        </>
      )}
    </div>
  );
}
