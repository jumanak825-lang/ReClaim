import { Bell } from "lucide-react";
import type { Schemas } from "@/lib/api/client";
import { fullDateTime, timeAgo } from "@/lib/labels";

/** Recent activity timeline. Bodies come from the API's privacy-safe notification text. */
export function ActivityList({ items, empty }: { items: Schemas["ActivityItem"][]; empty: string }) {
  if (!items.length) return <p className="text-muted-foreground">{empty}</p>;
  return (
    <ol className="divide-y rounded-lg border bg-card">
      {items.map((a, i) => (
        <li key={`${a.created_at}-${i}`} className="flex gap-3 p-4">
          <Bell className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="font-medium">{a.title}</p>
            <p className="text-sm text-muted-foreground">{a.body}</p>
          </div>
          <time dateTime={a.created_at} title={fullDateTime(a.created_at)} className="shrink-0 text-sm text-muted-foreground">
            {timeAgo(a.created_at)}
          </time>
        </li>
      ))}
    </ol>
  );
}
