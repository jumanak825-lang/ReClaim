"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { api, ApiError, unwrap } from "@/lib/api/client";
import { formatMoney } from "@/lib/labels";
import { ErrorState, LoadingState } from "@/components/states";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

/**
 * PayPal sends the browser here after approval. Arriving here proves nothing: the server captures
 * the order with PayPal and verifies amount, currency and status before anything is marked paid.
 */
export default function PayPalReturnPage() {
  const params = useSearchParams();
  const orderId = params.get("token");
  const recoveryId = params.get("recovery_id");
  const queryClient = useQueryClient();
  const started = useRef(false);

  const capture = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/payments/paypal/capture-order", { body: { paypal_order_id: orderId! } })),
    onSuccess: async (p) => {
      await queryClient.invalidateQueries({ queryKey: ["recoveries", p.recovery_id] });
      try {
        sessionStorage.removeItem(`reclaim:pay:${p.recovery_id}`);
      } catch {}
    },
  });
  const { mutate } = capture;
  useEffect(() => {
    if (orderId && !started.current) {
      started.current = true;
      mutate();
    }
  }, [orderId, mutate]);

  const backHref = recoveryId ? `/recoveries/${recoveryId}` : "/claims";
  if (!orderId) return <ErrorState title="Payment details missing" message="We couldn't tell which payment this was. Go back to your recovery and try again." />;
  if (capture.isIdle || capture.isPending) return <LoadingState label="Confirming your payment with PayPal…" />;
  if (capture.error) {
    const notApproved = capture.error instanceof ApiError && capture.error.code === "PAYMENT_NOT_APPROVED";
    return (
      <div className="mx-auto grid w-full max-w-lg gap-4">
        <Alert variant="destructive">
          <AlertTitle>{notApproved ? "Payment not completed" : "We couldn't confirm your payment"}</AlertTitle>
          <AlertDescription>
            {notApproved
              ? "PayPal hasn't approved this payment, so nothing was charged. You can try again from your recovery."
              : "Your delivery isn't marked as paid yet. If PayPal took the payment, it will be reconciled automatically."}
          </AlertDescription>
        </Alert>
        <Button asChild variant="outline" className="justify-self-start">
          <Link href={backHref}>Back to recovery</Link>
        </Button>
      </div>
    );
  }
  const p = capture.data;
  return (
    <div className="mx-auto grid w-full max-w-lg gap-4">
      <Alert>
        <CheckCircle2 aria-hidden />
        <AlertTitle>Payment confirmed</AlertTitle>
        <AlertDescription className="grid gap-2">
          <span>
            {formatMoney(p.amount_minor, p.currency)} received for delivery. Staff will prepare your item for dispatch.
          </span>
          {p.is_sandbox && <Badge variant="outline">PayPal Sandbox · no real money</Badge>}
        </AlertDescription>
      </Alert>
      <Button asChild className="justify-self-start">
        <Link href={`/recoveries/${p.recovery_id}`}>Continue to recovery</Link>
      </Button>
    </div>
  );
}
