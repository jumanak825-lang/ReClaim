"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { MapPin, Truck } from "lucide-react";
import { api, ApiError, unwrap } from "@/lib/api/client";
import { fieldErrors } from "@/lib/api/form-errors";
import { fromLocalInput } from "@/lib/datetime";
import { cn } from "@/lib/utils";
import { Field } from "@/components/auth/field";
import { useClaim } from "@/components/claims/use-claim";
import { ErrorState, LoadingState, PermissionDenied } from "@/components/states";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

type Method = "collection" | "delivery";
const emptyAddress = { recipient_name: "", line1: "", line2: "", city: "", region: "", postal_code: "", country_code: "" };

// Screen 12 (docs/02 §2.4): only after claim approval.
export default function ChooseRecoveryPage() {
  const { id } = useParams<{ id: string }>();
  const claim = useClaim(id);

  if (claim.isPending) return <LoadingState label="Loading…" />;
  if (claim.error) {
    return claim.error instanceof ApiError && claim.error.status === 404 ? (
      <PermissionDenied message="We couldn't find this claim." />
    ) : (
      <ErrorState onRetry={() => claim.refetch()} retrying={claim.isFetching} />
    );
  }
  const c = claim.data;
  if (c.recovery_id) {
    return (
      <PermissionDenied
        message="You've already chosen how to get this item back."
        action={
          <Button asChild variant="outline">
            <Link href={`/recoveries/${c.recovery_id}`}>View recovery</Link>
          </Button>
        }
      />
    );
  }
  if (!c.available_actions.includes("choose_recovery")) {
    return <PermissionDenied message="Collection or delivery becomes available once your claim is approved." />;
  }
  const f = c.match.found_item;
  return <ChooseForm claimId={c.id} itemLabel={f.item_label} where={[f.approximate_location, f.organisation_name].filter(Boolean).join(", ")} />;
}

function ChooseForm({ claimId, itemLabel, where }: { claimId: string; itemLabel: string; where: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [method, setMethod] = useState<Method | null>(null);
  const [windowStart, setWindowStart] = useState("");
  const [windowEnd, setWindowEnd] = useState("");
  const [addr, setAddr] = useState(emptyAddress);
  const [clientErrors, setClientErrors] = useState<Record<string, string>>({});

  const create = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/claims/{claim_id}/recoveries", {
          params: { path: { claim_id: claimId } },
          body:
            method === "collection"
              ? { method, preferred_window_start: fromLocalInput(windowStart), preferred_window_end: fromLocalInput(windowEnd) }
              : {
                  method: "delivery",
                  address: {
                    recipient_name: addr.recipient_name.trim(),
                    line1: addr.line1.trim(),
                    line2: addr.line2.trim() || null,
                    city: addr.city.trim(),
                    region: addr.region.trim() || null,
                    postal_code: addr.postal_code.trim() || null,
                    country_code: addr.country_code.trim().toUpperCase(),
                  },
                },
        }),
      ),
    onSuccess: async (rec) => {
      queryClient.setQueryData(["recoveries", rec.id], rec);
      await queryClient.invalidateQueries({ queryKey: ["claims"] });
      router.push(`/recoveries/${rec.id}`);
    },
  });
  const errors = { ...fieldErrors(create.error), ...clientErrors };
  const failure =
    create.error && !Object.keys(fieldErrors(create.error)).length
      ? create.error instanceof ApiError && create.error.code === "RECOVERY_EXISTS"
        ? "A recovery already exists for this claim."
        : "We couldn't save your choice. Try again."
      : null;

  function submit() {
    const e: Record<string, string> = {};
    if (!method) e.method = "Choose collection or delivery.";
    if (method === "delivery") {
      if (!addr.recipient_name.trim()) e.recipient_name = "Add the recipient's name.";
      if (!addr.line1.trim()) e.line1 = "Add the street address.";
      if (!addr.city.trim()) e.city = "Add the city.";
      if (!/^[A-Za-z]{2}$/.test(addr.country_code.trim())) e.country_code = "Use the two-letter country code, e.g. AE.";
    }
    if (method === "collection" && windowStart && windowEnd && windowEnd < windowStart) e.preferred_window_end = "This must be after the start.";
    setClientErrors(e);
    if (!Object.keys(e).length) create.mutate();
  }

  const setA = (k: keyof typeof emptyAddress) => (ev: React.ChangeEvent<HTMLInputElement>) => setAddr((a) => ({ ...a, [k]: ev.target.value }));
  const options: { value: Method; title: string; body: string; icon: typeof Truck }[] = [
    { value: "collection", title: "Collect it", body: `Pick it up at ${where}. Free. You'll get a one-time pickup code.`, icon: MapPin },
    { value: "delivery", title: "Have it delivered", body: "Pay a delivery fee with PayPal. You'll see the exact price before paying.", icon: Truck },
  ];

  return (
    <div className="mx-auto grid w-full max-w-2xl gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">How would you like to get your {itemLabel.toLowerCase()} back?</h1>
      <form
        noValidate
        className="grid gap-5 rounded-lg border bg-card p-5 sm:p-6"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        {failure && (
          <Alert variant="destructive">
            <AlertDescription>{failure}</AlertDescription>
          </Alert>
        )}
        <fieldset className="grid gap-2" aria-describedby={errors.method ? "method-error" : undefined}>
          <legend className="mb-1 text-sm font-medium">Choose one</legend>
          {options.map((o) => (
            <label
              key={o.value}
              className={cn(
                "flex cursor-pointer gap-3 rounded-md border p-3 has-[:checked]:border-primary has-[:checked]:bg-accent/50 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
              )}
            >
              <input type="radio" name="method" value={o.value} checked={method === o.value} onChange={() => setMethod(o.value)} className="mt-1 accent-[var(--primary)]" />
              <o.icon className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
              <span>
                <span className="block font-medium">{o.title}</span>
                <span className="block text-sm text-muted-foreground">{o.body}</span>
              </span>
            </label>
          ))}
          {errors.method && (
            <p id="method-error" className="text-sm text-destructive">
              {errors.method}
            </p>
          )}
        </fieldset>

        {method === "collection" && (
          <fieldset className="grid gap-4 sm:grid-cols-2">
            <legend className="mb-2 text-sm font-medium">Preferred collection time (optional)</legend>
            <Field id="window_start" label="From" type="datetime-local" value={windowStart} onChange={(e) => setWindowStart(e.target.value)} />
            <Field id="window_end" label="Until" type="datetime-local" value={windowEnd} onChange={(e) => setWindowEnd(e.target.value)} error={errors.preferred_window_end} />
          </fieldset>
        )}

        {method === "delivery" && (
          <fieldset className="grid gap-4">
            <legend className="mb-2 text-sm font-medium">Delivery address</legend>
            <p className="text-sm text-muted-foreground">Only shared with whoever fulfils the delivery, never with the finder.</p>
            <Field id="recipient_name" label="Recipient name" autoComplete="name" value={addr.recipient_name} onChange={setA("recipient_name")} maxLength={120} error={errors.recipient_name} />
            <Field id="line1" label="Address line 1" autoComplete="address-line1" value={addr.line1} onChange={setA("line1")} maxLength={200} error={errors.line1} />
            <Field id="line2" label="Address line 2 (optional)" autoComplete="address-line2" value={addr.line2} onChange={setA("line2")} maxLength={200} />
            <div className="grid gap-4 sm:grid-cols-2">
              <Field id="city" label="City" autoComplete="address-level2" value={addr.city} onChange={setA("city")} maxLength={100} error={errors.city} />
              <Field id="region" label="Region (optional)" autoComplete="address-level1" value={addr.region} onChange={setA("region")} maxLength={100} />
              <Field id="postal_code" label="Postal code (optional)" autoComplete="postal-code" value={addr.postal_code} onChange={setA("postal_code")} maxLength={20} />
              <Field
                id="country_code"
                label="Country code"
                hint="Two letters, e.g. AE, GB, US."
                autoComplete="country"
                value={addr.country_code}
                onChange={setA("country_code")}
                maxLength={2}
                error={errors.country_code}
              />
            </div>
          </fieldset>
        )}

        <div className="flex flex-wrap justify-between gap-2 border-t pt-4">
          <Button asChild variant="ghost">
            <Link href={`/claims/${claimId}`}>Back to claim</Link>
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Saving…" : method === "delivery" ? "Continue to price" : "Confirm"}
          </Button>
        </div>
      </form>
    </div>
  );
}
