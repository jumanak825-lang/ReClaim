"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError, unwrap, type Schemas } from "@/lib/api/client";
import { ErrorState, LoadingState, PermissionDenied } from "@/components/states";
import { Button } from "@/components/ui/button";

type Report = Schemas["ReportOut"];

/** Read ?id= and ?step= (1-based) for a wizard page. */
export function wizardParams(searchParams: URLSearchParams): { id: string | null; step: number } {
  const step = Number.parseInt(searchParams.get("step") ?? "1", 10) - 1;
  return { id: searchParams.get("id"), step: Number.isNaN(step) ? 0 : step };
}

/** Loads a report for a wizard to resume (draft) or edit (submitted), if the API allows editing. */
export function ResumeReport({
  id,
  type,
  children,
}: {
  id: string;
  type: Report["report_type"];
  children: (report: Report) => ReactNode;
}) {
  const report = useQuery({
    queryKey: ["reports", id],
    queryFn: () => unwrap(api.GET("/api/v1/reports/{report_id}", { params: { path: { report_id: id } } })),
  });

  if (report.isPending) return <LoadingState label="Loading your report…" />;
  if (report.error) {
    if (report.error instanceof ApiError && report.error.status === 404) {
      return <PermissionDenied message="We couldn't find that report." action={<BackToReports />} />;
    }
    return <ErrorState onRetry={() => report.refetch()} retrying={report.isFetching} />;
  }
  const r = report.data;
  if (r.report_type !== type || !r.available_actions.includes("edit")) {
    return <PermissionDenied message="This report can't be edited." action={<BackToReports />} />;
  }
  return children(r);
}

function BackToReports() {
  return (
    <Button asChild variant="outline">
      <Link href="/reports">Go to My reports</Link>
    </Button>
  );
}

/** Where a wizard (or "Continue draft") for this report lives. */
export function wizardHref(r: Pick<Report, "id" | "report_type">): string {
  return `/report/${r.report_type}?id=${r.id}`;
}
