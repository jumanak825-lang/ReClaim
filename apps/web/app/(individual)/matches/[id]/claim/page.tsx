"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { api, ApiError, rateLimitMessage, unwrap } from "@/lib/api/client";
import { fieldErrors } from "@/lib/api/form-errors";
import type { Image } from "@/lib/api/uploads";
import { Relevance } from "@/components/matches/match-card";
import { ImageUploader } from "@/components/reports/image-uploader";
import { TextArea } from "@/components/reports/fields";
import { ErrorState, LoadingState, PermissionDenied } from "@/components/states";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

const DONT_REMEMBER = "I don't remember";

// Screen 8, claim part (docs/02 §2.4; docs/06 §6.8): private questions, no hints from hidden details.
export default function ClaimPage() {
  const { id } = useParams<{ id: string }>();
  const match = useQuery({
    queryKey: ["matches", "detail", id],
    queryFn: () => unwrap(api.GET("/api/v1/matches/{match_id}", { params: { path: { match_id: id } } })),
  });
  const questions = useQuery({
    queryKey: ["matches", id, "questions"],
    queryFn: () => unwrap(api.GET("/api/v1/matches/{match_id}/verification-questions", { params: { path: { match_id: id } } })),
    enabled: !!match.data?.available_actions.includes("start_claim"),
  });

  if (match.isPending) return <LoadingState label="Loading…" />;
  if (match.error) {
    return match.error instanceof ApiError && match.error.status === 404 ? (
      <PermissionDenied message="We couldn't find this match." action={<BackToMatches />} />
    ) : (
      <ErrorState onRetry={() => match.refetch()} retrying={match.isFetching} />
    );
  }
  if (!match.data.available_actions.includes("start_claim")) {
    return (
      <PermissionDenied
        message={match.data.active_claim_id ? "You've already claimed this item." : "This item can't be claimed."}
        action={
          match.data.active_claim_id ? (
            <Button asChild variant="outline">
              <Link href={`/claims/${match.data.active_claim_id}`}>View your claim</Link>
            </Button>
          ) : (
            <BackToMatches />
          )
        }
      />
    );
  }
  if (questions.isPending) return <LoadingState label="Loading questions…" />;
  if (questions.error) return <ErrorState onRetry={() => questions.refetch()} retrying={questions.isFetching} />;

  return <ClaimForm matchId={id} itemLabel={match.data.found_item.item_label} questions={questions.data} relevance={<Relevance match={match.data} />} />;
}

function BackToMatches() {
  return (
    <Button asChild variant="outline">
      <Link href="/matches">Go to matches</Link>
    </Button>
  );
}

function ClaimForm({
  matchId,
  itemLabel,
  questions,
  relevance,
}: {
  matchId: string;
  itemLabel: string;
  questions: { id: string; prompt: string; allow_dont_remember?: boolean }[];
  relevance: React.ReactNode;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [statement, setStatement] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [dontRemember, setDontRemember] = useState<Record<string, boolean>>({});
  const [evidence, setEvidence] = useState<Image[]>([]);
  const [clientError, setClientError] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/matches/{match_id}/claims", {
          params: { path: { match_id: matchId } },
          body: {
            statement: statement.trim(),
            answers: questions
              .map((q) => ({ question_id: q.id, answer: dontRemember[q.id] ? DONT_REMEMBER : (answers[q.id] ?? "").trim() }))
              .filter((a) => a.answer),
            evidence_image_ids: evidence.map((e) => e.id),
          },
        }),
      ),
    onSuccess: async (claim) => {
      queryClient.setQueryData(["claims", claim.id], claim);
      await queryClient.invalidateQueries({ queryKey: ["matches"] });
      await queryClient.invalidateQueries({ queryKey: ["claims", "mine"] });
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      router.push(`/claims/${claim.id}?submitted=1`);
    },
  });

  const errors = fieldErrors(submit.error);
  const failure =
    rateLimitMessage(submit.error) ??
    (submit.error instanceof ApiError
      ? submit.error.code === "CLAIM_ALREADY_ACTIVE"
        ? "There's already an open claim for this item."
        : submit.error.code === "CLAIM_NOT_SUPPORTED"
          ? "Claims on items kept by individual finders aren't supported in this demo."
          : !Object.keys(errors).length
            ? "We couldn't submit your claim. Your answers are still here. Try again."
            : null
      : submit.error
        ? "We couldn't submit your claim. Try again."
        : null);

  return (
    <div className="mx-auto grid w-full max-w-2xl gap-6">
      <div className="grid gap-2">
        <h1 className="text-[1.75rem] leading-tight font-bold md:text-[2rem]">Claim this item: {itemLabel}</h1>
        {relevance}
      </div>

      <Alert>
        <Lock aria-hidden />
        <AlertDescription>
          Your answers and evidence are private. Only you and authorised staff at the organisation holding the item can
          see them. The finder never sees them. A person reviews every claim; AI only helps them compare details.
        </AlertDescription>
      </Alert>

      <form
        noValidate
        className="grid gap-5 surface p-5 sm:p-6"
        onSubmit={(e) => {
          e.preventDefault();
          if (!statement.trim()) {
            setClientError("Tell us why you believe this is yours.");
            return;
          }
          setClientError(null);
          submit.mutate();
        }}
      >
        {failure && (
          <Alert variant="destructive">
            <AlertDescription>{failure}</AlertDescription>
          </Alert>
        )}
        <TextArea
          label="Why do you believe this is yours?"
          hint="For example, when and where you last had it."
          value={statement}
          onChange={setStatement}
          maxLength={2000}
          error={clientError ?? errors.statement}
        />

        <fieldset className="grid gap-5">
          <legend className="mb-1 font-medium">Private verification questions</legend>
          <p className="text-sm text-muted-foreground">
            Answer what you can. It&apos;s fine to say you don&apos;t remember; don&apos;t guess.
          </p>
          {questions.map((q) => (
            <div key={q.id} className="grid gap-2">
              <TextArea
                label={q.prompt}
                value={dontRemember[q.id] ? "" : (answers[q.id] ?? "")}
                onChange={(v) => setAnswers((a) => ({ ...a, [q.id]: v }))}
                maxLength={1000}
              />
              {q.allow_dont_remember !== false && (
                <div className="flex items-center gap-2">
                  <Checkbox
                    id={`dr-${q.id}`}
                    checked={!!dontRemember[q.id]}
                    onCheckedChange={(v) => setDontRemember((d) => ({ ...d, [q.id]: v === true }))}
                  />
                  <Label htmlFor={`dr-${q.id}`} className="font-normal">
                    I don&apos;t remember
                  </Label>
                </div>
              )}
            </div>
          ))}
        </fieldset>

        <ImageUploader
          label="Supporting evidence (optional)"
          hint="A receipt, an earlier photo of you with the item, or a photo of the box. Kept private."
          visibility="private_evidence"
          images={evidence}
          onChange={setEvidence}
        />

        <div className="flex flex-wrap justify-between gap-2 border-t pt-4">
          <Button asChild variant="ghost">
            <Link href={`/matches/${matchId}`}>Cancel</Link>
          </Button>
          <Button type="submit" disabled={submit.isPending}>
            {submit.isPending ? "Submitting…" : "Submit claim"}
          </Button>
        </div>
      </form>
    </div>
  );
}
