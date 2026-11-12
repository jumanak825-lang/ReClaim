"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useOrg } from "@/components/organisation/org-shell";
import { RecoveryPage } from "@/components/recoveries/recovery-page";
import { Button } from "@/components/ui/button";

export default function StaffRecoveryPage() {
  const { recoveryId } = useParams<{ recoveryId: string }>();
  const org = useOrg();
  return (
    <RecoveryPage
      id={recoveryId}
      backLink={{ href: `/org/${org.organisation_slug}/operations`, label: "Operations" }}
      back={
        <Button asChild variant="outline">
          <Link href={`/org/${org.organisation_slug}`}>Back to overview</Link>
        </Button>
      }
    />
  );
}
