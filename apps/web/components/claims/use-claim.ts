"use client";

import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/lib/api/client";

export function useClaim(id: string) {
  return useQuery({
    queryKey: ["claims", id],
    queryFn: () => unwrap(api.GET("/api/v1/claims/{claim_id}", { params: { path: { claim_id: id } } })),
  });
}
