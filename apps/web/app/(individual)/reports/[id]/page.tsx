"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { EyeOff, Info, Loader2, Search } from "lucide-react";
import { api, ApiError, unwrap, type Schemas } from "@/lib/api/client";
import { categoryLabel, custodyLabel, fullDateTime, humanizeKey } from "@/lib/labels";
import { ReportStatusBadge } from "@/components/reports/report-status-badge";
import { wizardHref } from "@/components/reports/resume-report";
import { ErrorState, LoadingState, PermissionDenied } from "@/components/states";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type Report = Schemas["ReportOut"];

// Screen 6 (docs/02 §2.4).
export default function ReportDetailPage() {
  const { id } = useParams<{ id: string }>();
  const report = useQuery({
    queryKey: ["reports", id],
    queryFn: () => unwrap(api.GET("/api/v1/reports/{report_id}", { params: { path: { report_id: id } } })),
    // Keep the AI/matching state current while the report is being processed.
    refetchInterval: (q) => (q.state.data?.processing_status === "processing" ? 2000 : false),
  });

  if (report.isPending) return <LoadingState label="Loading report…" />;
  if (report.error) {
    if (report.error instanceof ApiError && report.error.status === 404) {
      return (
        <PermissionDenied
          message="We couldn't find this report, or you don't have access to it."
          action={
            <Button asChild variant="outline">
              <Link href="/reports">Go to My reports</Link>
            </Button>
          }
        />
      );
    }
    return <ErrorState onRetry={() => report.refetch()} retrying={report.isFetching} />;
  }
  return <ReportDetail r={report.data} />;
}

function ReportDetail({ r }: { r: Report }) {
  const isOwnerView = r.viewer_access !== "public";
  const editHref = wizardHref(r);
  const when =
    r.report_type === "lost"
      ? r.lost_at_start
        ? [r.lost_at_start, r.lost_at_end].filter(Boolean).map((t) => fullDateTime(t!)).join(" – ")
        : "Not sure"
      : r.found_at
        ? fullDateTime(r.found_at)
        : "Not given";

  return (
    <div className="mx-auto grid w-full max-w-3xl gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="grid gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">{r.report_type === "lost" ? "Lost report" : "Found report"}</Badge>
            <ReportStatusBadge status={r.status} />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">{r.item_label}</h1>
          <p className="text-sm text-muted-foreground">Reported {fullDateTime(r.created_at)}</p>
        </div>
        <Actions r={r} editHref={editHref} />
      </div>

      {r.status === "draft" && (
        <Alert>
          <Info aria-hidden />
          <AlertTitle>This report is a draft</AlertTitle>
          <AlertDescription>It isn&apos;t being matched yet. Continue and submit it when you&apos;re ready.</AlertDescription>
        </Alert>
      )}
      {r.processing_status === "processing" && (
        <p className="flex items-center gap-2 rounded-lg border bg-card p-4" role="status">
          <Loader2 className="size-4 animate-spin text-primary" aria-hidden />
          Looking for possible matches across participating locations…
        </p>
      )}
      {!isOwnerView && (
        <Alert>
          <Info aria-hidden />
          <AlertDescription>You&apos;re seeing the public details of this report. Private details are hidden.</AlertDescription>
        </Alert>
      )}

      {isOwnerView && r.status !== "draft" && r.processing_status === "completed" && (
        <MatchesSummary count={r.match_count} href={r.report_type === "lost" ? `/matches?report=${r.id}` : null} />
      )}

      <section aria-labelledby="details-heading" className="grid gap-3 rounded-lg border bg-card p-5">
        <h2 id="details-heading" className="font-semibold">
          Details
        </h2>
        <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[10rem_1fr]">
          <dt className="text-muted-foreground">Category</dt>
          <dd>{categoryLabel[r.category]}</dd>
          <dt className="text-muted-foreground">Description</dt>
          <dd className="whitespace-pre-line">{r.description}</dd>
          {(r.brand || r.model) && (
            <>
              <dt className="text-muted-foreground">Brand / model</dt>
              <dd>{[r.brand, r.model].filter(Boolean).join(" ")}</dd>
            </>
          )}
          {Object.entries(r.attributes_public).map(([k, v]) => (
            <Row key={k} label={humanizeKey(k)} value={v} />
          ))}
          <dt className="text-muted-foreground">{r.report_type === "lost" ? "Last seen" : "Found at"}</dt>
          <dd>{r.location?.name && r.organisation ? `${r.location.name}, ${r.organisation.name}` : r.location_label}</dd>
          <dt className="text-muted-foreground">{r.report_type === "lost" ? "Lost" : "Found"}</dt>
          <dd>{when}</dd>
          {r.custody_status && <Row label="Custody" value={custodyLabel[r.custody_status]} />}
        </dl>
      </section>

      {r.images.length > 0 && (
        <section aria-labelledby="photos-heading" className="grid gap-3">
          <h2 id="photos-heading" className="font-semibold">
            Photos
          </h2>
          <ul className="flex flex-wrap gap-3">
            {r.images.map((img, i) => (
              <li key={img.id}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={img.url} alt={`${r.item_label}, photo ${i + 1}`} className="size-32 rounded-md border object-cover" />
              </li>
            ))}
          </ul>
        </section>
      )}

      {r.attributes_private && (
        <section aria-labelledby="private-heading" className="grid gap-3 rounded-lg border border-dashed p-5">
          <h2 id="private-heading" className="flex items-center gap-1.5 font-semibold">
            <EyeOff className="size-4" aria-hidden /> Private details
          </h2>
          <p className="text-sm text-muted-foreground">Only visible to you and authorised reviewers.</p>
          {Object.keys(r.attributes_private).length || r.storage_reference ? (
            <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[10rem_1fr]">
              {Object.entries(r.attributes_private).map(([k, v]) => (
                <Row key={k} label={humanizeKey(k)} value={v} />
              ))}
              {r.storage_reference && <Row label="Storage reference" value={r.storage_reference} />}
            </dl>
          ) : (
            <p className="text-sm">None added.</p>
          )}
        </section>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{value}</dd>
    </>
  );
}

function MatchesSummary({ count, href }: { count: number; href: string | null }) {
  return (
    <section aria-labelledby="matches-heading" className="flex gap-3 rounded-lg border bg-accent/40 p-4">
      <Search className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden />
      <div>
        <h2 id="matches-heading" className="font-semibold">
          {count === 0 ? "No possible matches yet" : count === 1 ? "1 possible match" : `${count} possible matches`}
        </h2>
        <p className="text-sm text-muted-foreground">
          {count === 0
            ? "We'll keep looking and notify you if a possible match appears."
            : "AI-suggested candidates, not proof of ownership. You'll prove ownership privately if you make a claim."}
        </p>
        {count > 0 && href && (
          <Button asChild size="sm" className="mt-3">
            <Link href={href}>View possible matches</Link>
          </Button>
        )}
      </div>
    </section>
  );
}

function Actions({ r, editHref }: { r: Report; editHref: string }) {
  const queryClient = useQueryClient();
  const withdraw = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/reports/{report_id}/withdraw", { params: { path: { report_id: r.id } } })),
    onSuccess: (updated) => {
      queryClient.setQueryData(["reports", r.id], updated);
      void queryClient.invalidateQueries({ queryKey: ["me"] });
      void queryClient.invalidateQueries({ queryKey: ["reports", "mine"] });
    },
  });
  const canEdit = r.available_actions.includes("edit");
  const canWithdraw = r.available_actions.includes("withdraw");
  if (!canEdit && !canWithdraw) return null;

  const withdrawError =
    withdraw.error instanceof ApiError && withdraw.error.code === "REPORT_HAS_ACTIVE_CLAIM"
      ? "This report has an open claim. It can't be withdrawn until the claim is resolved."
      : withdraw.error
        ? "We couldn't withdraw this report. Try again."
        : null;

  return (
    <div className="grid justify-items-end gap-2">
      <div className="flex gap-2">
        {canEdit && (
          <Button asChild variant="outline">
            <Link href={editHref}>{r.status === "draft" ? "Continue draft" : "Edit"}</Link>
          </Button>
        )}
        {canWithdraw && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="ghost" disabled={withdraw.isPending}>
                {withdraw.isPending ? "Withdrawing…" : "Withdraw"}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Withdraw this report?</AlertDialogTitle>
                <AlertDialogDescription>
                  It will stop being matched and you can&apos;t reopen it. You can create a new report later.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Keep report</AlertDialogCancel>
                <AlertDialogAction variant="destructive" onClick={() => withdraw.mutate()}>
                  Withdraw report
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
      </div>
      {withdrawError && (
        <p className="text-sm text-destructive" role="alert">
          {withdrawError}
        </p>
      )}
    </div>
  );
}
