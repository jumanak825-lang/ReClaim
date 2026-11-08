"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ApiError } from "@/lib/api/client";
import { useMe } from "@/lib/api/me";
import { ErrorState, LoadingState } from "@/components/states";

/** Renders children only once the API confirms the session. A 401 sends the user to sign-in. */
export function AuthGate({ children }: { children: ReactNode }) {
  const me = useMe();
  const router = useRouter();
  const pathname = usePathname();
  const signedOut = me.error instanceof ApiError && me.error.code === "UNAUTHENTICATED";

  useEffect(() => {
    if (signedOut) router.replace(`/sign-in?next=${encodeURIComponent(pathname)}`);
  }, [signedOut, router, pathname]);

  if (me.isPending || signedOut) return <LoadingState />;
  if (me.error) return <ErrorState onRetry={() => me.refetch()} retrying={me.isFetching} />;
  return children;
}
