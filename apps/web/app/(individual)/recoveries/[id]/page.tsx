"use client";

import { useParams } from "next/navigation";
import { RecoveryPage } from "@/components/recoveries/recovery-page";

export default function ClaimantRecoveryPage() {
  const { id } = useParams<{ id: string }>();
  return <RecoveryPage id={id} backLink={{ href: "/claims", label: "My claims" }} />;
}
