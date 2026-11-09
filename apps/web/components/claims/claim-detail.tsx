"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, EyeOff, FileText, History } from "lucide-react";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import type { Image } from "@/lib/api/uploads";
import { claimStatusLabel, fullDateTime } from "@/lib/labels";
import { ClaimStatusBadge } from "@/components/claims/claim-status-badge";
import { Relevance } from "@/components/matches/match-card";
import { ImageUploader } from "@/components/reports/image-uploader";
import { TextArea } from "@/components/reports/fields";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export type Claim = Schemas["ClaimOut"];

/**
 * Claim status (claimant) and claim detail (reviewers). Private sections render only when the API
 * returned them for this viewer; `reviewPanel` is the organisation's decision UI.
 */
export function ClaimDetail({ claim, justSubmitted, reviewPanel }: { claim: Claim; justSubmitted?: boolean; reviewPanel?: ReactNode }) {
  const c = claim;
  const isClaimant = c.viewer_role === "claimant";
  return (
    <div className="mx-auto grid w-full max-w-3xl gap-6">
      <div className="grid gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <ClaimStatusBadge status={c.status} />
          <span className="text-sm text-muted-foreground">Reference {c.reference}</span>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">Claim for {c.match.found_item.item_label.toLowerCase()}</h1>
        <p className="text-sm text-muted-foreground">
          Submitted {fullDateTime(c.created_at)}
          {c.claimant_display_name && ` by ${c.claimant_display_name}`}
        </p>
      </div>

      {justSubmitted && isClaimant && (
        <Alert>
          <CheckCircle2 aria-hidden />
          <AlertTitle>Claim submitted</AlertTitle>
          <AlertDescription>
            Your reference is {c.reference}. Authorised staff will review it and we&apos;ll notify you of the decision.
          </AlertDescription>
        </Alert>
      )}

      {isClaimant && <ClaimantNextStep c={c} />}
      {reviewPanel}

      <section aria-labelledby="match-heading" className="grid gap-2 rounded-lg border bg-card p-4">
        <h2 id="match-heading" className="font-semibold">
          Match
        </h2>
        <p className="text-sm">
          Lost report: {c.match.lost_item.item_label} · Found item: {c.match.found_item.item_label}
          {c.match.found_item.organisation_name && ` at ${c.match.found_item.approximate_location}, ${c.match.found_item.organisation_name}`}
        </p>
        <Relevance match={c.match} />
      </section>

      {c.statement !== null && <PrivateSubmission c={c} />}
      {isClaimant && c.available_actions.includes("add_evidence") && <AddEvidence claimId={c.id} />}

      <section aria-labelledby="history-heading" className="grid gap-3">
        <h2 id="history-heading" className="flex items-center gap-1.5 font-semibold">
          <History className="size-4" aria-hidden /> History
        </h2>
        <ol className="grid gap-3 border-l pl-4">
          {c.history.map((h, i) => (
            <li key={`${h.created_at}-${i}`} className="grid gap-0.5">
              <p className="text-sm font-medium">
                {h.from_status ? `${claimStatusLabel[h.from_status]} → ` : ""}
                {claimStatusLabel[h.to_status]}
                {h.actor_display_name && <span className="font-normal text-muted-foreground"> · {h.actor_display_name}</span>}
              </p>
              {h.reason && <p className="text-sm">“{h.reason}”</p>}
              <time dateTime={h.created_at} className="text-xs text-muted-foreground">
                {fullDateTime(h.created_at)}
              </time>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}

function ClaimantNextStep({ c }: { c: Claim }) {
  if (c.status === "approved") {
    return (
      <Alert>
        <CheckCircle2 aria-hidden />
        <AlertTitle>Your claim was approved</AlertTitle>
        <AlertDescription className="grid gap-3">
          {c.decision_reason && <span>Reviewer&apos;s note: “{c.decision_reason}”</span>}
          {c.available_actions.includes("choose_recovery") && (
            <Button asChild className="justify-self-start">
              <Link href={`/claims/${c.id}/recovery`}>Choose collection or delivery</Link>
            </Button>
          )}
          {c.available_actions.includes("view_recovery") && c.recovery_id && (
            <Button asChild variant="outline" className="justify-self-start">
              <Link href={`/recoveries/${c.recovery_id}`}>View recovery</Link>
            </Button>
          )}
        </AlertDescription>
      </Alert>
    );
  }
  if (c.status === "rejected") {
    return (
      <Alert>
        <AlertTitle>Your claim wasn&apos;t approved</AlertTitle>
        <AlertDescription>{c.decision_reason ?? "The reviewer couldn't confirm ownership."}</AlertDescription>
      </Alert>
    );
  }
  return (
    <p className="rounded-lg border bg-card p-4 text-sm">
      {c.status === "escalated"
        ? "Your claim needs a further look by a senior reviewer. You can still add evidence."
        : "Waiting for review. You can add more evidence while it's being reviewed."}
    </p>
  );
}

function PrivateSubmission({ c }: { c: Claim }) {
  return (
    <section aria-labelledby="private-heading" className="grid gap-4 rounded-lg border border-dashed p-5">
      <div className="grid gap-1">
        <h2 id="private-heading" className="flex items-center gap-1.5 font-semibold">
          <EyeOff className="size-4" aria-hidden /> {c.viewer_role === "claimant" ? "Your private answers and evidence" : "Claimant's answers and evidence"}
        </h2>
        <p className="text-sm text-muted-foreground">Only the claimant and authorised reviewers can see this.</p>
      </div>
      <div className="grid gap-1">
        <h3 className="text-sm font-medium">Statement</h3>
        <p className="text-sm whitespace-pre-line">{c.statement}</p>
      </div>
      {c.answers.length > 0 && (
        <dl className="grid gap-3">
          {c.answers.map((a) => (
            <div key={a.question_id} className="grid gap-0.5">
              <dt className="text-sm font-medium">{a.prompt}</dt>
              <dd className="text-sm whitespace-pre-line">{a.answer}</dd>
            </div>
          ))}
        </dl>
      )}
      <div className="grid gap-2">
        <h3 className="text-sm font-medium">Evidence</h3>
        {c.evidence.length ? (
          <ul className="flex flex-wrap gap-3">
            {c.evidence.map((e) => (
              <li key={e.id} className="grid max-w-56 gap-1 text-sm">
                {e.image ? (
                  e.image.content_type === "application/pdf" ? (
                    <a href={e.image.url} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-primary underline-offset-4 hover:underline">
                      <FileText className="size-4" aria-hidden /> PDF document
                    </a>
                  ) : (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={e.image.url} alt="Claim evidence" className="size-28 rounded-md border object-cover" />
                  )
                ) : null}
                {e.text && <p className="whitespace-pre-line">{e.text}</p>}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">None added.</p>
        )}
      </div>
    </section>
  );
}

function AddEvidence({ claimId }: { claimId: string }) {
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const [images, setImages] = useState<Image[]>([]);
  const add = useMutation({
    mutationFn: async () => {
      let latest: Claim | undefined;
      for (const img of images) {
        latest = await unwrap(
          api.POST("/api/v1/claims/{claim_id}/evidence", { params: { path: { claim_id: claimId } }, body: { evidence_type: "photo", image_id: img.id } }),
        );
      }
      if (text.trim()) {
        latest = await unwrap(
          api.POST("/api/v1/claims/{claim_id}/evidence", { params: { path: { claim_id: claimId } }, body: { evidence_type: "text", text: text.trim() } }),
        );
      }
      return latest;
    },
    onSuccess: (latest) => {
      if (latest) queryClient.setQueryData(["claims", claimId], latest);
      setText("");
      setImages([]);
    },
  });

  return (
    <section aria-labelledby="add-evidence-heading" className="grid gap-4 rounded-lg border bg-card p-5">
      <h2 id="add-evidence-heading" className="font-semibold">
        Add evidence
      </h2>
      <TextArea label="Note for the reviewer (optional)" value={text} onChange={setText} maxLength={2000} />
      <ImageUploader label="Photos (optional)" hint="Kept private, like the rest of your claim." visibility="private_evidence" images={images} onChange={setImages} />
      {add.error && (
        <p className="text-sm text-destructive" role="alert">
          We couldn&apos;t add your evidence. Try again.
        </p>
      )}
      {add.isSuccess && !add.isPending && (
        <p className="text-sm text-success" role="status">
          Evidence added.
        </p>
      )}
      <Button className="justify-self-start" onClick={() => add.mutate()} disabled={add.isPending || (!text.trim() && !images.length)}>
        {add.isPending ? "Adding…" : "Add evidence"}
      </Button>
    </section>
  );
}
