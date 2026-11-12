"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ImageOff } from "lucide-react";
import { api, ApiError, unwrap, type Schemas } from "@/lib/api/client";
import { categoryLabel, dateRange, humanizeKey, matchStatusLabel } from "@/lib/labels";
import { ConfirmAction } from "@/components/confirm-action";
import { Relevance, type Match } from "@/components/matches/match-card";
import { ErrorState, LoadingState, PermissionDenied } from "@/components/states";
import { BackLink } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

// Screen 8 (docs/02 §2.4): side-by-side safe attributes, why it may match, claim or dismiss.
export default function MatchDetailPage() {
  const { id } = useParams<{ id: string }>();
  const match = useQuery({
    queryKey: ["matches", "detail", id],
    queryFn: () => unwrap(api.GET("/api/v1/matches/{match_id}", { params: { path: { match_id: id } } })),
  });

  if (match.isPending) return <LoadingState label="Loading match…" />;
  if (match.error) {
    if (match.error instanceof ApiError && match.error.status === 404) {
      return (
        <PermissionDenied
          message="We couldn't find this match, or you don't have access to it."
          action={
            <Button asChild variant="outline">
              <Link href="/matches">Go to matches</Link>
            </Button>
          }
        />
      );
    }
    return <ErrorState onRetry={() => match.refetch()} retrying={match.isFetching} />;
  }
  return <MatchDetail m={match.data} />;
}

function MatchDetail({ m }: { m: Match }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const dismiss = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/matches/{match_id}/dismiss", { params: { path: { match_id: m.id } } })),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["matches"] });
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      router.push("/matches");
    },
  });

  return (
    <div className="mx-auto grid w-full max-w-4xl gap-6">
      <BackLink href="/matches">Possible matches</BackLink>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="grid gap-2">
          <Badge variant="outline">{matchStatusLabel[m.status]}</Badge>
          <h1 className="text-[1.75rem] leading-tight font-bold md:text-[2rem]">Possible match: {m.found_item.item_label}</h1>
          <Relevance match={m} />
        </div>
        <div className="flex flex-wrap gap-2">
          {m.available_actions.includes("start_claim") && (
            <Button asChild>
              <Link href={`/matches/${m.id}/claim`}>Claim this item</Link>
            </Button>
          )}
          {m.available_actions.includes("view_claim") && m.active_claim_id && (
            <Button asChild variant="outline">
              <Link href={`/claims/${m.active_claim_id}`}>View your claim</Link>
            </Button>
          )}
          {m.available_actions.includes("dismiss") && (
            <ConfirmAction
              trigger="Not my item"
              triggerVariant="ghost"
              title="Dismiss this match?"
              description="It will be removed from your matches. We'll keep looking for other possible matches."
              confirmLabel="Not my item"
              onConfirm={() => dismiss.mutateAsync()}
              pending={dismiss.isPending}
              error={dismiss.error ? "We couldn't dismiss this match. Try again." : null}
            />
          )}
        </div>
      </div>

      <section aria-labelledby="why-heading" className="grid gap-2 surface-ai p-5">
        <h2 id="why-heading" className="font-semibold">
          Why this may match
        </h2>
        <ul className="grid gap-1.5">
          {m.explanation.map((e) => (
            <li key={e} className="flex gap-2 text-sm">
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden /> {e}
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted-foreground">
          Scores are unvalidated demo values from matcher {m.matcher_version}. Only public details are compared here.
        </p>
      </section>

      <section aria-labelledby="compare-heading" className="grid gap-3">
        <h2 id="compare-heading" className="font-semibold">
          Side by side
        </h2>
        <div className="grid gap-4 md:grid-cols-2">
          <ItemSummary title="Your lost report" item={m.lost_item} />
          <ItemSummary title="Found item" item={m.found_item} />
        </div>
        <p className="text-sm text-muted-foreground">
          The exact storage location and the finder&apos;s private details are never shown here. If your claim is
          approved, you&apos;ll get collection or delivery details.
        </p>
      </section>
    </div>
  );
}

function ItemSummary({ title, item }: { title: string; item: Schemas["MatchItemSummary"] }) {
  return (
    <div className="grid content-start gap-3 surface p-4">
      <h3 className="font-medium">{title}</h3>
      {item.thumbnail_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={item.thumbnail_url} alt={`${title}: ${item.item_label}`} className="aspect-video w-full rounded-md border object-cover" />
      ) : (
        <div className="flex aspect-video w-full items-center justify-center rounded-md border bg-muted text-sm text-muted-foreground">
          <ImageOff className="mr-2 size-4" aria-hidden /> No photo
        </div>
      )}
      <dl className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-muted-foreground">Item</dt>
        <dd>{item.item_label}</dd>
        <dt className="text-muted-foreground">Category</dt>
        <dd>{categoryLabel[item.category]}</dd>
        <dt className="text-muted-foreground">Where</dt>
        <dd>
          {item.approximate_location}
          {item.organisation_name && ` (${item.organisation_name})`}
        </dd>
        <dt className="text-muted-foreground">When</dt>
        <dd>{dateRange(item.date_start, item.date_end)}</dd>
        {Object.entries(item.attributes_public).map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-muted-foreground">{humanizeKey(k)}</dt>
            <dd>{String(v)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
