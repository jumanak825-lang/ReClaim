"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { ApiError } from "@/lib/api/client";
import { ClaimDetail } from "@/components/claims/claim-detail";
import { useClaim } from "@/components/claims/use-claim";
import { ErrorState, LoadingState, PermissionDenied } from "@/components/states";
import { Button } from "@/components/ui/button";

export default function ClaimPage() {
  const { id } = useParams<{ id: string }>();
  const submitted = useSearchParams().get("submitted") === "1";
  const claim = useClaim(id);

  if (claim.isPending) return <LoadingState label="Loading claim…" />;
  if (claim.error) {
    return claim.error instanceof ApiError && claim.error.status === 404 ? (
      <PermissionDenied
        message="We couldn't find this claim, or you don't have access to it."
        action={
          <Button asChild variant="outline">
            <Link href="/claims">Go to My claims</Link>
          </Button>
        }
      />
    ) : (
      <ErrorState onRetry={() => claim.refetch()} retrying={claim.isFetching} />
    );
  }
  return <ClaimDetail claim={claim.data} justSubmitted={submitted} back={{ href: "/claims", label: "My claims" }} />;
}
