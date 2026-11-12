import Link from "next/link";
import { ImageOff, ShieldAlert, Sparkles } from "lucide-react";
import type { Schemas } from "@/lib/api/client";
import { categoryLabel, dateRange, matchStatusLabel } from "@/lib/labels";
import { Badge } from "@/components/ui/badge";

export type Match = Schemas["MatchOut"];

export const OWNERSHIP_WARNING = "This is an AI-generated candidate, not proof of ownership.";

/** "AI relevance 87 · Strong potential match", always next to the ownership caveat (FR-012). */
export function Relevance({ match }: { match: Match }) {
  return (
    <div className="grid gap-2">
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-brand/30 bg-accent px-2.5 py-0.5 font-medium text-accent-foreground">
          <Sparkles className="size-3.5" aria-hidden />
          AI relevance <strong className="tabular-nums">{Math.round(match.score)}</strong>
        </span>
        <span className="text-muted-foreground">{match.label}</span>
      </p>
      <p className="flex items-start gap-1.5 text-sm font-medium">
        <ShieldAlert className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />
        {match.ownership_warning ?? OWNERSHIP_WARNING}
      </p>
    </div>
  );
}

/** Candidate card for the owner: shows the found item's public-safe summary only. */
export function MatchCard({ match }: { match: Match }) {
  const f = match.found_item;
  return (
    <li className="surface">
      <Link href={`/matches/${match.id}`} className="flex gap-4 p-4 hover:bg-muted/40 focus-visible:bg-muted/40">
        {f.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={f.thumbnail_url} alt={`Found ${f.item_label}`} className="size-20 shrink-0 rounded-md border object-cover" />
        ) : (
          <div className="flex size-20 shrink-0 items-center justify-center rounded-md border bg-muted" aria-hidden>
            <ImageOff className="size-5 text-muted-foreground" />
          </div>
        )}
        <div className="grid min-w-0 flex-1 gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">Found item: {f.item_label}</span>
            <Badge variant="outline">{matchStatusLabel[match.status]}</Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            {categoryLabel[f.category]} · {f.approximate_location}
            {f.organisation_name && ` (${f.organisation_name})`} · {dateRange(f.date_start, f.date_end)}
          </p>
          <p className="text-sm">For your report: {match.lost_item.item_label}</p>
          <Relevance match={match} />
        </div>
      </Link>
    </li>
  );
}
