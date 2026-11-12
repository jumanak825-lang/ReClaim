"use client";

import { useRouter } from "next/navigation";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, BellDot } from "lucide-react";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { useMe } from "@/lib/api/me";
import { fullDateTime, timeAgo } from "@/lib/labels";
import { notificationHref } from "@/lib/notification-href";
import { cn } from "@/lib/utils";
import { unreadCountKey } from "@/components/notifications/notification-bell";
import { ErrorState, LoadingState } from "@/components/states";
import { EmptyState, PageHeader } from "@/components/page";
import { Button } from "@/components/ui/button";

type Notification = Schemas["NotificationOut"];

// Screen 14 (docs/02 §2.4). Bodies are the API's privacy-safe text.
export default function NotificationsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: me } = useMe();

  const list = useInfiniteQuery({
    queryKey: ["notifications", "list"],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) => {
      const res = await api.GET("/api/v1/notifications", { params: { query: { limit: 20, ...(pageParam ? { cursor: pageParam } : {}) } } });
      const items = await unwrap(Promise.resolve(res));
      return { items, next: res.data?.meta.next_cursor ?? undefined };
    },
    getNextPageParam: (last) => last.next,
  });
  const items = list.data?.pages.flatMap((p) => p.items) ?? [];

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["notifications"] });
  };
  const readOne = useMutation({
    mutationFn: (id: string) => unwrap(api.POST("/api/v1/notifications/{notification_id}/read", { params: { path: { notification_id: id } } })),
    onSuccess: (count) => queryClient.setQueryData(unreadCountKey, count),
    onSettled: refresh,
  });
  const readAll = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/notifications/read-all")),
    onSettled: refresh,
  });

  function open(n: Notification) {
    if (!n.read_at) readOne.mutate(n.id);
    const href = notificationHref(n, me);
    if (href) router.push(href);
  }

  return (
    <div className="mx-auto grid w-full max-w-3xl gap-6">
      <PageHeader
        title="Notifications"
        actions={
          items.some((n) => !n.read_at) && (
            <Button variant="outline" onClick={() => readAll.mutate()} disabled={readAll.isPending}>
              {readAll.isPending ? "Marking…" : "Mark all as read"}
            </Button>
          )
        }
      />
      {list.isPending ? (
        <LoadingState label="Loading notifications…" />
      ) : list.error ? (
        <ErrorState onRetry={() => list.refetch()} retrying={list.isFetching} />
      ) : !items.length ? (
        <EmptyState icon={Bell} title="No notifications yet">
          We&apos;ll let you know about matches, claim decisions and recovery updates.
        </EmptyState>
      ) : (
        <>
          <ul className="divide-y surface">
            {items.map((n) => {
              const unread = !n.read_at;
              const href = notificationHref(n, me);
              return (
                <li key={n.id}>
                  <button
                    type="button"
                    onClick={() => open(n)}
                    disabled={!href && !unread}
                    className={cn("flex w-full gap-3 p-4 text-left transition-colors hover:bg-muted/60 disabled:cursor-default md:px-5", unread && "bg-accent/60")}
                  >
                    {unread ? <BellDot className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden /> : <Bell className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />}
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium">
                        {n.title}
                        {unread && <span className="sr-only"> (unread)</span>}
                      </span>
                      <span className="block text-sm text-muted-foreground">{n.body}</span>
                    </span>
                    <time dateTime={n.created_at} title={fullDateTime(n.created_at)} className="shrink-0 text-sm text-muted-foreground">
                      {timeAgo(n.created_at)}
                    </time>
                  </button>
                </li>
              );
            })}
          </ul>
          {list.hasNextPage && (
            <Button variant="outline" className="justify-self-center" onClick={() => list.fetchNextPage()} disabled={list.isFetchingNextPage}>
              {list.isFetchingNextPage ? "Loading…" : "Load more"}
            </Button>
          )}
        </>
      )}
      <p className="text-sm text-muted-foreground">Notifications are in-app only in this demo; email isn&apos;t set up.</p>
    </div>
  );
}
