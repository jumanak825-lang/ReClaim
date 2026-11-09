"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock, KeyRound, MapPin, Package, Truck } from "lucide-react";
import { api, ApiError, unwrap, type Schemas } from "@/lib/api/client";
import { formatMoney, fullDateTime, recoveryStatusLabel } from "@/lib/labels";
import { ConfirmAction } from "@/components/confirm-action";
import { Field } from "@/components/auth/field";
import { TextArea } from "@/components/reports/fields";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export type Recovery = Schemas["RecoveryOut"];

function errorText(e: unknown): string | null {
  if (!e) return null;
  if (e instanceof ApiError) {
    switch (e.code) {
      case "INVALID_PICKUP_TOKEN":
        return "That pickup code isn't valid. Check it with the claimant.";
      case "PICKUP_TOKEN_EXPIRED":
        return "The pickup code has expired.";
      case "REFUND_REQUIRED":
        return "Delivery was already paid. Refunds aren't available in this demo.";
      case "RECOVERY_INVALID_STATE":
        return "This action isn't available any more. Refresh to see the latest status.";
      case "PAYMENT_PROVIDER_UNAVAILABLE":
        return "PayPal is unavailable right now. Try again shortly.";
    }
  }
  return "Something went wrong. Try again.";
}

/** Recovery detail (Screen 13) for the claimant and for organisation staff. Actions come from the API. */
export function RecoveryDetail({ recovery }: { recovery: Recovery }) {
  const r = recovery;
  const isClaimant = r.viewer_role === "claimant";
  return (
    <div className="mx-auto grid w-full max-w-3xl gap-6">
      <div className="grid gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={r.status === "completed" ? "default" : "outline"} className={r.status === "completed" ? "bg-success text-success-foreground" : undefined}>
            {r.status === "completed" ? <CheckCircle2 aria-hidden /> : <Clock aria-hidden />} {recoveryStatusLabel[r.status]}
          </Badge>
          <Badge variant="outline">{r.method === "collection" ? "Collection" : "Delivery"}</Badge>
          <span className="text-sm text-muted-foreground">Claim {r.claim_reference}</span>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">Recovery: {r.item_label}</h1>
      </div>

      {r.status === "completed" && (
        <Alert>
          <CheckCircle2 aria-hidden />
          <AlertTitle>{isClaimant ? "Your item is back with you" : "Recovery complete"}</AlertTitle>
          <AlertDescription>The case is closed.</AlertDescription>
        </Alert>
      )}

      {r.method === "collection" && r.collection && <CollectionCard r={r} />}
      {r.method === "delivery" && <DeliveryCard r={r} />}

      {isClaimant ? <ClaimantActions r={r} /> : <StaffActions r={r} />}

      <section aria-labelledby="timeline-heading" className="grid gap-3">
        <h2 id="timeline-heading" className="font-semibold">
          Timeline
        </h2>
        <ol className="grid gap-3 border-l pl-4">
          {r.timeline.map((e, i) => (
            <li key={`${e.created_at}-${i}`} className="grid gap-0.5">
              <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
                {e.description}
                {e.is_simulated && <Badge variant="outline">Simulated</Badge>}
              </p>
              <time dateTime={e.created_at} className="text-xs text-muted-foreground">
                {fullDateTime(e.created_at)}
              </time>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}

function CollectionCard({ r }: { r: Recovery }) {
  const c = r.collection!;
  return (
    <section aria-labelledby="collection-heading" className="grid gap-2 rounded-lg border bg-card p-4">
      <h2 id="collection-heading" className="flex items-center gap-1.5 font-semibold">
        <MapPin className="size-4" aria-hidden /> Collection
      </h2>
      <p className="text-sm">
        <strong>
          {c.location_name}, {c.organisation_name}
        </strong>
        {c.address_public && <span className="block text-muted-foreground">{c.address_public}</span>}
      </p>
      {c.opening_hours && <p className="text-sm">Opening hours: {c.opening_hours}</p>}
      {c.instructions && <p className="text-sm">{c.instructions}</p>}
      {c.preferred_window_start && (
        <p className="text-sm text-muted-foreground">
          Your preferred time: {fullDateTime(c.preferred_window_start)}
          {c.preferred_window_end && ` – ${fullDateTime(c.preferred_window_end)}`}
        </p>
      )}
    </section>
  );
}

function DeliveryCard({ r }: { r: Recovery }) {
  const a = r.delivery_address;
  const q = r.delivery_quote;
  return (
    <section aria-labelledby="delivery-heading" className="grid gap-3 rounded-lg border bg-card p-4">
      <h2 id="delivery-heading" className="flex items-center gap-1.5 font-semibold">
        <Truck className="size-4" aria-hidden /> Delivery
        {r.courier_is_simulated && <Badge variant="outline">Simulated courier</Badge>}
      </h2>
      {a && (
        <address className="text-sm not-italic">
          {a.recipient_name}
          {[a.line1, a.line2, a.city, a.region, a.postal_code, a.country_code].filter(Boolean).map((x) => (
            <span key={x} className="block">
              {x}
            </span>
          ))}
          {r.viewer_role === "staff" && !a.line1 && (
            <span className="block text-xs text-muted-foreground">Full address hidden: only shown to fulfilment.</span>
          )}
        </address>
      )}
      {q && (
        <p className="text-sm">
          Delivery fee: <strong>{formatMoney(q.amount_minor, q.currency)}</strong> ({q.is_estimate ? "estimate" : "fixed price"}) ·{" "}
          {q.service_description}
        </p>
      )}
      {r.payment && (
        <p className="flex flex-wrap items-center gap-2 text-sm">
          Payment: <strong>{r.payment.status === "captured" ? "Paid" : r.payment.status}</strong>
          {r.payment.is_sandbox && <Badge variant="outline">PayPal Sandbox · no real money</Badge>}
        </p>
      )}
      {r.tracking_reference && <p className="text-sm">Tracking reference: {r.tracking_reference} (simulated)</p>}
      <p className="text-xs text-muted-foreground">The delivery fee covers delivery only. It isn&apos;t a reward for the finder.</p>
    </section>
  );
}

function useRecoveryAction<T>(r: Recovery, fn: (arg: T) => Promise<Recovery>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: async (updated) => {
      queryClient.setQueryData(["recoveries", r.id], updated);
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      await queryClient.invalidateQueries({ queryKey: ["org"] });
      await queryClient.invalidateQueries({ queryKey: ["claims"] });
    },
  });
}

const path = (r: Recovery) => ({ params: { path: { recovery_id: r.id } } });

function ClaimantActions({ r }: { r: Recovery }) {
  const [shownCode, setShownCode] = useState<{ token: string; expires: string | null } | null>(null);
  const pay = usePay(r);
  const showCode = useRecoveryAction(r, async () => {
    const updated = await unwrap(api.POST("/api/v1/recoveries/{recovery_id}/collection/pickup-token", path(r)));
    setShownCode({ token: updated.pickup_token ?? "", expires: updated.pickup_token_expires_at });
    return updated;
  });
  const received = useRecoveryAction(r, () => unwrap(api.POST("/api/v1/recoveries/{recovery_id}/confirm-received", path(r))));
  const a = r.available_actions;
  if (!a.length) return null;

  return (
    <section aria-label="Your next step" className="grid gap-3 rounded-lg border bg-accent/30 p-4">
      {a.includes("pay_with_paypal") && r.delivery_quote && (
        <div className="grid gap-2">
          <p className="text-sm">
            Pay the delivery fee of <strong>{formatMoney(r.delivery_quote.amount_minor, r.delivery_quote.currency)}</strong> with PayPal.
            The payment is confirmed by Reclaim&apos;s server, not by this page.
          </p>
          <Button className="justify-self-start" onClick={() => pay.mutate()} disabled={pay.isPending || pay.isSuccess}>
            {pay.isPending || pay.isSuccess ? "Opening PayPal…" : "Pay with PayPal (Sandbox)"}
          </Button>
          {pay.error && <p className="text-sm text-destructive" role="alert">{errorText(pay.error)}</p>}
        </div>
      )}
      {a.includes("show_pickup_code") && (
        <div className="grid gap-2">
          {shownCode ? (
            <div className="grid justify-items-start gap-1 rounded-md border bg-card p-4">
              <p className="flex items-center gap-1.5 text-sm font-medium">
                <KeyRound className="size-4" aria-hidden /> Your one-time pickup code
              </p>
              <p className="font-mono text-3xl tracking-widest" aria-live="polite">
                {shownCode.token}
              </p>
              {shownCode.expires && <p className="text-sm text-muted-foreground">Valid until {fullDateTime(shownCode.expires)}</p>}
              <p className="text-sm">Show it at the desk with photo ID. Don&apos;t share it or post it anywhere.</p>
            </div>
          ) : (
            <p className="text-sm">Your item is ready. Show your pickup code at the desk.</p>
          )}
          <Button variant={shownCode ? "outline" : "default"} className="justify-self-start" onClick={() => showCode.mutate(undefined)} disabled={showCode.isPending}>
            {showCode.isPending ? "Creating code…" : shownCode ? "Create a new code" : "Show pickup code"}
          </Button>
          {shownCode && <p className="text-xs text-muted-foreground">Creating a new code stops the old one from working.</p>}
          {showCode.error && <p className="text-sm text-destructive" role="alert">{errorText(showCode.error)}</p>}
        </div>
      )}
      {a.includes("confirm_received") && (
        <div className="grid gap-2">
          <p className="flex items-center gap-1.5 text-sm">
            <Package className="size-4" aria-hidden /> Once the item arrives, confirm you&apos;ve received it.
          </p>
          <ConfirmAction
            trigger="I've received my item"
            triggerVariant="default"
            title="Confirm you've received the item?"
            description="This completes the recovery and closes the case."
            confirmLabel="Confirm received"
            onConfirm={() => received.mutateAsync(undefined)}
            pending={received.isPending}
            error={errorText(received.error)}
          />
        </div>
      )}
      {a.includes("cancel") && <CancelRecovery r={r} />}
    </section>
  );
}

function StaffActions({ r }: { r: Recovery }) {
  const [token, setToken] = useState("");
  const ready = useRecoveryAction(r, () => unwrap(api.POST("/api/v1/recoveries/{recovery_id}/collection/confirm", path(r))));
  const validate = useRecoveryAction(r, () =>
    unwrap(api.POST("/api/v1/recoveries/{recovery_id}/collection/validate-token", { ...path(r), body: { token: token.trim() } })),
  );
  const dispatch = useRecoveryAction(r, () => unwrap(api.POST("/api/v1/recoveries/{recovery_id}/delivery/dispatch", path(r))));
  const a = r.available_actions;
  if (!a.length) return null;

  return (
    <section aria-label="Staff actions" className="grid gap-4 rounded-lg border bg-accent/30 p-4">
      {a.includes("mark_ready_for_pickup") && (
        <div className="grid gap-2">
          <p className="text-sm">When the item is at the desk, mark it ready. The claimant can then get their pickup code.</p>
          <Button className="justify-self-start" onClick={() => ready.mutate(undefined)} disabled={ready.isPending}>
            {ready.isPending ? "Saving…" : "Mark ready for pickup"}
          </Button>
          {ready.error && <p className="text-sm text-destructive" role="alert">{errorText(ready.error)}</p>}
        </div>
      )}
      {a.includes("validate_pickup_token") && (
        <form
          className="grid gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (token.trim()) validate.mutate(undefined);
          }}
        >
          <Field
            id="pickup-code"
            label="Claimant's pickup code"
            hint="Check photo ID as your policy requires, then enter the code they show you."
            value={token}
            onChange={(e) => setToken(e.target.value)}
            autoComplete="off"
            maxLength={20}
            error={errorText(validate.error) ?? undefined}
          />
          <Button type="submit" className="justify-self-start" disabled={validate.isPending || !token.trim()}>
            {validate.isPending ? "Checking…" : "Validate and hand over"}
          </Button>
        </form>
      )}
      {a.includes("dispatch") && (
        <div className="grid gap-2">
          <p className="text-sm">Delivery is paid. Dispatch the item with the courier (simulated in this demo).</p>
          <Button className="justify-self-start" onClick={() => dispatch.mutate(undefined)} disabled={dispatch.isPending}>
            {dispatch.isPending ? "Dispatching…" : "Dispatch (simulated courier)"}
          </Button>
          {dispatch.error && <p className="text-sm text-destructive" role="alert">{errorText(dispatch.error)}</p>}
        </div>
      )}
      {a.includes("cancel") && <CancelRecovery r={r} />}
    </section>
  );
}

function CancelRecovery({ r }: { r: Recovery }) {
  const [reason, setReason] = useState("");
  const cancel = useRecoveryAction(r, () =>
    unwrap(api.POST("/api/v1/recoveries/{recovery_id}/cancel", { ...path(r), body: { reason: reason.trim() } })),
  );
  return (
    <div>
      <ConfirmAction
        trigger="Cancel recovery"
        triggerVariant="ghost"
        title="Cancel this recovery?"
        description="The item stays with the organisation. This can't be undone here."
        confirmLabel="Cancel recovery"
        destructive
        canConfirm={reason.trim().length >= 3}
        onConfirm={() => cancel.mutateAsync(undefined)}
        pending={cancel.isPending}
        error={errorText(cancel.error)}
      >
        <TextArea label="Reason (required)" value={reason} onChange={setReason} maxLength={500} required />
      </ConfirmAction>
    </div>
  );
}

/**
 * Create the PayPal order on the server (amount comes from the stored quote, never the browser),
 * then send the browser to PayPal. The idempotency key is kept per recovery so a retried click
 * returns the same order instead of creating a second one.
 */
function usePay(r: Recovery) {
  return useMutation({
    mutationFn: async () => {
      const storageKey = `reclaim:pay:${r.id}`;
      let key: string | null = null;
      try {
        key = sessionStorage.getItem(storageKey);
      } catch {}
      if (!key) {
        key = crypto.randomUUID();
        try {
          sessionStorage.setItem(storageKey, key);
        } catch {}
      }
      return unwrap(api.POST("/api/v1/payments/paypal/create-order", { body: { recovery_id: r.id, idempotency_key: key } }));
    },
    onSuccess: (order) => window.location.assign(order.approval_url),
  });
}
