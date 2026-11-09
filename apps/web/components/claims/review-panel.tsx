"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Info, Sparkles } from "lucide-react";
import { api, ApiError, unwrap } from "@/lib/api/client";
import { ConfirmAction } from "@/components/confirm-action";
import { TextArea } from "@/components/reports/fields";
import type { Claim } from "./claim-detail";

type Decision = "approved" | "rejected" | "escalated";
const MIN_REASON = 10;

const decisions: { action: string; decision: Decision; label: string; title: string; description: string; destructive?: boolean }[] = [
  {
    action: "approve",
    decision: "approved",
    label: "Approve",
    title: "Approve this claim?",
    description: "The claimant becomes the confirmed owner and can arrange collection or delivery. Only one claim per item can be approved.",
  },
  {
    action: "reject",
    decision: "rejected",
    label: "Reject",
    title: "Reject this claim?",
    description: "The claimant is told the claim wasn't approved. The item stays available for other claims.",
    destructive: true,
  },
  {
    action: "escalate",
    decision: "escalated",
    label: "Escalate",
    title: "Escalate this claim?",
    description: "Send it for a further look by a senior reviewer before a final decision.",
  },
];

/** AI assistance (clearly not a decision) plus approve / reject / escalate with a required reason. */
export function ReviewPanel({ claim }: { claim: Claim }) {
  const c = claim;
  if (c.viewer_role === "staff") {
    return (
      <p className="rounded-lg border bg-card p-4 text-sm">
        <Info className="mr-1.5 inline size-4" aria-hidden /> Only reviewers can see the claimant&apos;s evidence and decide claims.
      </p>
    );
  }
  return (
    <div className="grid gap-4">
      {c.ai_assist && <AiAssist assist={c.ai_assist} />}
      {c.available_actions.some((a) => decisions.some((d) => d.action === a)) && <Decide claim={c} />}
      {c.status !== "pending" && c.status !== "escalated" && c.decision_reason && (
        <p className="rounded-lg border bg-card p-4 text-sm">
          Decision reason: “{c.decision_reason}”
        </p>
      )}
    </div>
  );
}

function AiAssist({ assist }: { assist: NonNullable<Claim["ai_assist"]> }) {
  return (
    <section aria-labelledby="ai-assist-heading" className="grid gap-2 rounded-lg border border-dashed bg-accent/30 p-4">
      <h2 id="ai-assist-heading" className="flex items-center gap-1.5 font-semibold">
        <Sparkles className="size-4 text-primary" aria-hidden /> AI assistance (not a decision)
      </h2>
      <p className="text-sm">{assist.summary}</p>
      {assist.flags.length > 0 && (
        <ul className="grid gap-1.5">
          {assist.flags.map((f, i) => (
            <li key={i} className="flex gap-2 text-sm">
              {f.severity === "warning" ? (
                <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning-foreground" aria-label="Warning" />
              ) : (
                <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-label="Note" />
              )}
              {f.message}
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-muted-foreground">{assist.disclaimer ?? "AI assistance only. A human reviewer makes the decision."}</p>
    </section>
  );
}

function Decide({ claim }: { claim: Claim }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const review = useMutation({
    mutationFn: (decision: Decision) =>
      unwrap(api.POST("/api/v1/claims/{claim_id}/review", { params: { path: { claim_id: claim.id } }, body: { decision, reason: reason.trim() } })),
    onSuccess: async (updated) => {
      queryClient.setQueryData(["claims", claim.id], updated);
      setReason("");
      await queryClient.invalidateQueries({ queryKey: ["org"] });
    },
  });
  const error =
    review.error instanceof ApiError
      ? review.error.code === "FOUND_ITEM_ALREADY_CLAIMED"
        ? "Another claim on this item has already been approved."
        : review.error.code === "CLAIM_NOT_REVIEWABLE"
          ? "This claim was already decided. Refresh to see the latest status."
          : review.error.code === "SELF_REVIEW_FORBIDDEN"
            ? "You can't review your own claim."
            : "We couldn't record the decision. Try again."
      : review.error
        ? "We couldn't record the decision. Try again."
        : null;
  const valid = reason.trim().length >= MIN_REASON;

  return (
    <section aria-labelledby="decide-heading" className="grid gap-3 rounded-lg border bg-card p-4">
      <h2 id="decide-heading" className="font-semibold">
        Decision
      </h2>
      <p className="text-sm text-muted-foreground">
        Compare the claimant&apos;s private answers with the item&apos;s recorded private details. Your decision and reason are
        recorded in the audit log.
      </p>
      <div className="flex flex-wrap gap-2">
        {decisions
          .filter((d) => claim.available_actions.includes(d.action))
          .map((d) => (
            <ConfirmAction
              key={d.action}
              trigger={d.label}
              triggerVariant={d.action === "approve" ? "default" : "outline"}
              title={d.title}
              description={d.description}
              confirmLabel={d.label}
              destructive={d.destructive}
              canConfirm={valid}
              pending={review.isPending}
              error={error}
              onConfirm={() => review.mutateAsync(d.decision)}
            >
              <TextArea
                label="Reason (required)"
                hint={`At least ${MIN_REASON} characters. The claimant sees this for approvals and rejections.`}
                value={reason}
                onChange={setReason}
                maxLength={1000}
                required
              />
            </ConfirmAction>
          ))}
      </div>
    </section>
  );
}
