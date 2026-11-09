"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export default function PayPalCancelPage() {
  const recoveryId = useSearchParams().get("recovery_id");
  return (
    <div className="mx-auto grid w-full max-w-lg gap-4">
      <Alert>
        <AlertTitle>Payment cancelled</AlertTitle>
        <AlertDescription>Nothing was charged. You can pay whenever you&apos;re ready, or choose another option.</AlertDescription>
      </Alert>
      <Button asChild variant="outline" className="justify-self-start">
        <Link href={recoveryId ? `/recoveries/${recoveryId}` : "/claims"}>Back to recovery</Link>
      </Button>
    </div>
  );
}
