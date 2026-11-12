"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ApiError } from "@/lib/api/client";
import { ClaimDetail } from "@/components/claims/claim-detail";
import { ReviewPanel } from "@/components/claims/review-panel";
import { useClaim } from "@/components/claims/use-claim";
import { useOrg } from "@/components/organisation/org-shell";
import { ErrorState, LoadingState, PermissionDenied } from "@/components/states";
import { Button } from "@/components/ui/button";

export default function OrgClaimPage() {
  const { claimId } = useParams<{ claimId: string }>();
  const org = useOrg();
  const claim = useClaim(claimId);
  const back = (
    <Button asChild variant="outline">
      <Link href={`/org/${org.organisation_slug}/claims`}>Back to claims</Link>
    </Button>
  );

  if (claim.isPending) return <LoadingState label="Loading claim…" />;
  if (claim.error) {
    // 404 also covers claims outside this reviewer's organisation or locations.
    return claim.error instanceof ApiError && claim.error.status === 404 ? (
      <PermissionDenied message="We couldn't find this claim in your organisation." action={back} />
    ) : (
      <ErrorState onRetry={() => claim.refetch()} retrying={claim.isFetching} />
    );
  }
  return (
    <ClaimDetail
      claim={claim.data}
      reviewPanel={<ReviewPanel claim={claim.data} />}
      back={{ href: `/org/${org.organisation_slug}/claims`, label: "All claims" }}
    />
  );
}
