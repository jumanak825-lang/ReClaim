"use client";

import Link from "next/link";
import { Bell } from "lucide-react";
import { useMe } from "@/lib/api/me";
import { notificationHref } from "@/lib/notification-href";
import type { Schemas } from "@/lib/api/client";
import { fullDateTime, timeAgo } from "@/lib/labels";

/** Recent activity timeline. Bodies come from the API's privacy-safe notification text. */
export function ActivityList({ items, empty }: { items: Schemas["ActivityItem"][]; empty: string }) {
  const { data: me } = useMe();
  if (!items.length) return <p className="surface p-5 text-muted-foreground">{empty}</p>;
  return (
    <ol className="divide-y surface">
      {items.map((a, i) => {
        const href = notificationHref(a, me);
        return (
          <li key={`${a.created_at}-${i}`} className="flex gap-4 p-4 md:px-5">
            <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-accent text-brand" aria-hidden>
              <Bell className="size-4" />
            </span>
            <div className="min-w-0 flex-1">
              {href ? (
                <Link href={href} className="font-semibold underline-offset-4 hover:underline">
                  {a.title}
                </Link>
              ) : (
                <p className="font-semibold">{a.title}</p>
              )}
              <p className="text-sm text-muted-foreground">{a.body}</p>
            </div>
            <time dateTime={a.created_at} title={fullDateTime(a.created_at)} className="shrink-0 text-sm text-muted-foreground">
              {timeAgo(a.created_at)}
            </time>
          </li>
        );
      })}
    </ol>
  );
}
