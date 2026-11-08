"use client";

import { useQuery } from "@tanstack/react-query";
import { api, unwrap, type Schemas } from "./client";

export type Me = Schemas["MeOut"];
export type Membership = Schemas["MembershipOut"];

export const meQueryKey = ["me"] as const;

/** The signed-in user, from the API. A 401 surfaces as ApiError code UNAUTHENTICATED. */
export function useMe() {
  return useQuery({ queryKey: meQueryKey, queryFn: () => unwrap(api.GET("/api/v1/me")) });
}

/** Where to land after sign-in when no `next` was requested. */
export function homeFor(me: Me): string {
  const first = me.memberships[0];
  return first ? `/org/${first.organisation_slug}` : "/dashboard";
}
