"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError, unwrap } from "@/lib/api/client";
import { LostWizard } from "@/components/reports/lost-wizard";
import { ErrorState, LoadingState, PermissionDenied } from "@/components/states";
import { Button } from "@/components/ui/button";

export default function ReportLostPage() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id");
  if (!id) return <LostWizard />;
  // ?step= is 1-based in the URL.
  const step = Number.parseInt(searchParams.get("step") ?? "1", 10) - 1;
  return <ResumeLost id={id} step={Number.isNaN(step) ? 0 : step} />;
}

/** `?id=` resumes a draft, or edits a submitted report the API still lets the owner edit. */
function ResumeLost({ id, step }: { id: string; step: number }) {
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
  if (r.report_type !== "lost" || !r.available_actions.includes("edit")) {
    return <PermissionDenied message="This report can't be edited." action={<BackToReports />} />;
  }
  // key: start fresh if the id in the URL changes.
  return <LostWizard key={r.id} existing={r} initialStep={step} />;
}

function BackToReports() {
  return (
    <Button asChild variant="outline">
      <Link href="/reports">Go to My reports</Link>
    </Button>
  );
}
