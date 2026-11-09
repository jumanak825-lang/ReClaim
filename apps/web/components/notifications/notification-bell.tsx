"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { api, unwrap } from "@/lib/api/client";
import { Button } from "@/components/ui/button";

export const unreadCountKey = ["notifications", "unread-count"] as const;

export function NotificationBell() {
  const unread = useQuery({
    queryKey: unreadCountKey,
    queryFn: () => unwrap(api.GET("/api/v1/notifications/unread-count")),
    refetchInterval: 30_000,
  });
  const count = unread.data?.unread ?? 0;
  return (
    <Button asChild variant="ghost" size="sm" className="relative">
      <Link href="/notifications" aria-label={count ? `Notifications, ${count} unread` : "Notifications"}>
        <Bell aria-hidden />
        {count > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-4 rounded-full bg-primary px-1 text-center text-[10px] leading-4 font-semibold text-primary-foreground" aria-hidden>
            {count > 9 ? "9+" : count}
          </span>
        )}
      </Link>
    </Button>
  );
}
