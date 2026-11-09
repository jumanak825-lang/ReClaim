"use client";

import type { ReactNode } from "react";
import { ApiError } from "@/lib/api/client";
import { ErrorState, LoadingState, PermissionDenied } from "@/components/states";
import { RecoveryDetail } from "./recovery-detail";
import { useRecovery } from "./use-recovery";

export function RecoveryPage({ id, back }: { id: string; back?: ReactNode }) {
  const recovery = useRecovery(id);
  if (recovery.isPending) return <LoadingState label="Loading recovery…" />;
  if (recovery.error) {
    return recovery.error instanceof ApiError && recovery.error.status === 404 ? (
      <PermissionDenied message="We couldn't find this recovery, or you don't have access to it." action={back} />
    ) : (
      <ErrorState onRetry={() => recovery.refetch()} retrying={recovery.isFetching} />
    );
  }
  return <RecoveryDetail recovery={recovery.data} />;
}
