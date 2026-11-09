"use client";

import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/lib/api/client";

export function useRecovery(id: string) {
  return useQuery({
    queryKey: ["recoveries", id],
    queryFn: () => unwrap(api.GET("/api/v1/recoveries/{recovery_id}", { params: { path: { recovery_id: id } } })),
    // The simulated courier moves on by itself after dispatch; keep the timeline current.
    refetchInterval: (q) => (q.state.data && ["dispatched", "in_transit"].includes(q.state.data.status) ? 5000 : false),
  });
}
