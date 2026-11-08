"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Eye, EyeOff, Hand, ShieldAlert } from "lucide-react";
import { api, ApiError, unwrap, type Schemas } from "@/lib/api/client";
import { fieldErrors } from "@/lib/api/form-errors";
import { useMe, type Membership } from "@/lib/api/me";
import type { Image } from "@/lib/api/uploads";
import { fromLocalInput, toLocalInput } from "@/lib/datetime";
import { categoryLabel, custodyLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";
import { Field } from "@/components/auth/field";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AiSuggestions, type SuggestionField } from "./ai-suggestions";
import { CategorySelect, FieldShell, TextArea, describedBy, type Category } from "./fields";
import { ImageUploader } from "./image-uploader";
import { Stepper } from "./stepper";

type Report = Schemas["ReportOut"];
type Custody = "finder_holds" | "transferred" | "organisation_holds";

// Custody comes before location: for organisation custody the listing uses the organisation's
// location, and custody can't be changed once the draft exists (the API's PATCH doesn't take it).
const STEPS = ["Item and photo", "Who has it now", "Where and when", "Visible details", "Private details", "Review suggestions", "Submit"];
const DRAFT_STEP = 2;

const PRIVATE_FIELDS = [
  { key: "distinctive_marks", label: "Distinctive marks, stickers or damage" },
  { key: "contents", label: "Contents or attached items" },
  { key: "serial_number", label: "Serial number or engraving" },
] as const;

type FoundForm = {
  category: Category | "";
  item_label: string;
  description: string;
  images: Image[];
  custody: Custody | "";
  orgId: string;
  locationId: string;
  place: string;
  foundAt: string;
  brand: string;
  model: string;
  colour: string;
  private: Record<string, string>;
  storageRef: string;
};

function nowLocal() {
  return toLocalInput(new Date().toISOString());
}

function fromReport(r: Report): FoundForm {
  return {
    category: r.category,
    item_label: r.item_label,
    description: r.description,
    images: r.images,
    custody: (r.custody_status === "released" ? "" : r.custody_status) ?? "",
    orgId: r.organisation?.id ?? "",
    locationId: r.location?.id ?? "",
    place: r.organisation ? "" : r.location_label,
    foundAt: toLocalInput(r.found_at),
    brand: r.brand ?? "",
    model: r.model ?? "",
    colour: r.attributes_public.colour ?? "",
    private: { ...(r.attributes_private ?? {}) },
    storageRef: r.storage_reference ?? "",
  };
}

const isOrgCustody = (c: FoundForm["custody"]) => c === "transferred" || c === "organisation_holds";

function commonPayload(f: FoundForm, isStaff: boolean) {
  const privateAttrs: Record<string, string> = Object.fromEntries(
    Object.entries(f.private)
      .map(([k, v]) => [k, v.trim()] as const)
      .filter(([, v]) => v),
  );
  const publicAttrs: Record<string, string> = f.colour.trim() ? { colour: f.colour.trim().toLowerCase() } : {};
  return {
    category: f.category as Category,
    item_label: f.item_label.trim(),
    description: f.description.trim(),
    brand: f.brand.trim() || null,
    model: f.model.trim() || null,
    found_at: fromLocalInput(f.foundAt),
    attributes_public: publicAttrs,
    attributes_private: privateAttrs,
    image_ids: f.images.map((i) => i.id),
    // The API only accepts a storage reference from the holding organisation's staff.
    ...(isStaff ? { storage_reference: f.storageRef.trim() || null } : {}),
  };
}

function validate(step: number, f: FoundForm): Record<string, string> {
  const e: Record<string, string> = {};
  if (step === 0) {
    if (!f.category) e.category = "Choose a category.";
    if (!f.item_label.trim()) e.item_label = "Say what the item is.";
    if (!f.description.trim()) e.description = "Describe the item.";
  }
  if (step === 1) {
    if (!f.custody) e.custody = "Choose who has the item now.";
    if (isOrgCustody(f.custody) && !f.orgId) e.organisation_id = "Choose the organisation.";
    if (isOrgCustody(f.custody) && !f.locationId) e.location_id = "Choose the location.";
  }
  if (step === 2) {
    if (f.custody === "finder_holds" && !f.place.trim()) e.label = "Add where you found it. A place name is enough.";
    if (!f.foundAt) e.found_at = "Add roughly when you found it.";
    else if (new Date(f.foundAt).getTime() > Date.now() + 60_000) e.found_at = "This can't be in the future.";
  }
  return e;
}

/** Found report wizard (docs/02 Screen 5), for individual finders and organisation staff. */
export function FoundWizard({
  existing,
  initialStep = 0,
  preselectOrgSlug,
}: {
  existing?: Report;
  initialStep?: number;
  preselectOrgSlug?: string | null;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const { data: me } = useMe();
  const memberships = me?.memberships ?? [];
  const reportId = existing?.id ?? null;
  const isEdit = !!existing && existing.status !== "draft";

  const [form, setForm] = useState<FoundForm>(() => {
    if (existing) return fromReport(existing);
    const pre = memberships.find((m) => m.organisation_slug === preselectOrgSlug);
    const preLocs = pre?.location_ids ?? [];
    return {
      category: "",
      item_label: "",
      description: "",
      images: [],
      custody: pre ? "organisation_holds" : "",
      orgId: pre?.organisation_id ?? "",
      locationId: preLocs.length === 1 ? preLocs[0] : "",
      place: "",
      foundAt: nowLocal(),
      brand: "",
      model: "",
      colour: "",
      private: {},
      storageRef: "",
    };
  });
  const [step, setStep] = useState(Math.min(Math.max(initialStep, 0), existing ? STEPS.length - 1 : 0));
  const [clientErrors, setClientErrors] = useState<Record<string, string>>({});
  const headingRef = useRef<HTMLHeadingElement>(null);
  const firstRender = useRef(true);

  const membership = memberships.find((m) => m.organisation_id === form.orgId);
  const isStaff = isOrgCustody(form.custody) && !!membership;

  useEffect(() => {
    if (reportId) router.replace(`${pathname}?id=${reportId}&step=${step + 1}`, { scroll: false });
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    headingRef.current?.focus();
  }, [step, reportId, router, pathname]);

  const set = <K extends keyof FoundForm>(key: K, value: FoundForm[K]) => setForm((f) => ({ ...f, [key]: value }));

  const save = useMutation({
    mutationFn: async () => {
      const common = commonPayload(form, isStaff);
      if (!reportId) {
        return unwrap(
          api.POST("/api/v1/reports/found", {
            body: {
              ...common,
              custody_status: form.custody as Custody,
              ...(isOrgCustody(form.custody)
                ? { organisation_id: form.orgId, location_id: form.locationId }
                : { found_location: { label: form.place.trim() } }),
              as_draft: true,
            },
          }),
        );
      }
      return patch(reportId);
    },
    onSuccess: (r) => queryClient.setQueryData(["reports", r.id], r),
  });

  function patch(id: string) {
    const body = {
      ...commonPayload(form, isStaff),
      // Organisation-held items always use the organisation's location.
      ...(form.custody === "finder_holds" ? { last_location: { label: form.place.trim() } } : {}),
    };
    return unwrap(api.PATCH("/api/v1/reports/{report_id}", { params: { path: { report_id: id } }, body }));
  }

  const finish = useMutation({
    mutationFn: async () => {
      const saved = await patch(reportId!);
      if (isEdit) return saved;
      return unwrap(api.POST("/api/v1/reports/{report_id}/submit", { params: { path: { report_id: reportId! } } }));
    },
    onSuccess: async (r) => {
      queryClient.setQueryData(["reports", r.id], r);
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      await queryClient.invalidateQueries({ queryKey: ["reports", "mine"] });
      await queryClient.invalidateQueries({ queryKey: ["org"] });
      router.push(`/reports/${r.id}`);
    },
  });

  const serverErrors = { ...fieldErrors(save.error), ...fieldErrors(finish.error) };
  const errors = { ...serverErrors, ...clientErrors };
  const failure = save.error ?? finish.error;
  const failureMessage = failure && !Object.keys(serverErrors).length ? messageFor(failure) : null;

  async function next() {
    const e = validate(step, form);
    setClientErrors(e);
    if (Object.keys(e).length) return;
    if (step === DRAFT_STEP || (reportId && step === 4)) {
      let saved;
      try {
        saved = await save.mutateAsync();
      } catch {
        return;
      }
      if (!reportId) {
        router.replace(`${pathname}?id=${saved.id}&step=${DRAFT_STEP + 2}`, { scroll: false });
        return;
      }
    }
    setStep((s) => s + 1);
  }

  const busy = save.isPending || finish.isPending;
  const suggestionValues: Record<SuggestionField, string> = {
    category: form.category,
    item_label: form.item_label,
    brand: form.brand,
    model: form.model,
    colour: form.colour,
  };

  return (
    <div className="mx-auto grid w-full max-w-2xl gap-6">
      <div className="grid gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{isEdit ? "Edit your found report" : "Report something found"}</h1>
        <Stepper steps={STEPS} current={step} />
      </div>

      <form
        noValidate
        className="grid gap-5 rounded-lg border bg-card p-5 sm:p-6"
        onSubmit={(e) => {
          e.preventDefault();
          if (step < STEPS.length - 1) void next();
          else finish.mutate();
        }}
      >
        <h2 ref={headingRef} tabIndex={-1} className="text-lg font-semibold outline-none">
          {STEPS[step]}
        </h2>

        {failureMessage && (
          <Alert variant="destructive">
            <AlertDescription>{failureMessage}</AlertDescription>
          </Alert>
        )}

        {step === 0 && (
          <>
            <PublicWarning />
            <CategorySelect value={form.category} onChange={(c) => set("category", c)} error={errors.category} />
            <Field
              id="item_label"
              label="What is it?"
              placeholder="e.g. Laptop, wallet, set of keys"
              value={form.item_label}
              onChange={(e) => set("item_label", e.target.value)}
              maxLength={120}
              error={errors.item_label}
            />
            <TextArea
              label="Describe it"
              hint="What it looks like. Leave out serial numbers, names and anything inside it: those go in Private details."
              value={form.description}
              onChange={(v) => set("description", v)}
              maxLength={2000}
              error={errors.description}
            />
            <ImageUploader
              label="Photos (optional)"
              hint="Photos can be shown to people who may own it. Avoid showing ID cards, screens, serial numbers or anything inside."
              visibility="public_safe"
              images={form.images}
              onChange={(imgs) => set("images", imgs)}
            />
          </>
        )}

        {step === 1 && (
          <CustodyStep form={form} set={set} errors={errors} memberships={memberships} locked={!!reportId} />
        )}

        {step === 2 && (
          <>
            {form.custody === "finder_holds" ? (
              <Field
                id="place"
                label="Where did you find it?"
                hint="A place name is enough, e.g. “Gate B12, Terminal 1”. You can keep the item's current whereabouts private."
                value={form.place}
                onChange={(e) => set("place", e.target.value)}
                maxLength={200}
                error={errors.label}
              />
            ) : (
              <ListedLocation orgId={form.orgId} locationId={form.locationId} />
            )}
            <Field
              id="found_at"
              label="When did you find it?"
              type="datetime-local"
              value={form.foundAt}
              onChange={(e) => set("foundAt", e.target.value)}
              error={errors.found_at}
            />
          </>
        )}

        {step === 3 && (
          <>
            <p className="text-sm text-muted-foreground">Only add what anyone looking at the item could see.</p>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field id="brand" label="Brand (if visible)" value={form.brand} onChange={(e) => set("brand", e.target.value)} maxLength={80} />
              <Field id="model" label="Model (if visible)" value={form.model} onChange={(e) => set("model", e.target.value)} maxLength={80} />
              <Field id="colour" label="Main colour" value={form.colour} onChange={(e) => set("colour", e.target.value)} maxLength={40} />
            </div>
          </>
        )}

        {step === 4 && (
          <fieldset className="grid gap-4 rounded-md border border-dashed p-4">
            <legend className="flex items-center gap-1.5 px-1 text-sm font-medium">
              <EyeOff className="size-4" aria-hidden /> Private details
            </legend>
            <p className="text-sm text-muted-foreground">
              Never shown publicly. Reviewers use these to check that someone claiming the item really owns it, so note
              details only the owner would know.
            </p>
            {PRIVATE_FIELDS.map((p) => (
              <Field
                key={p.key}
                id={`private-${p.key}`}
                label={p.label}
                value={form.private[p.key] ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, private: { ...f.private, [p.key]: e.target.value } }))}
                maxLength={300}
              />
            ))}
            {isStaff && (
              <Field
                id="storage_ref"
                label="Storage reference (staff only)"
                hint="Where it's stored, e.g. “Shelf C4, bin 12”. Visible only to your organisation. Never include door or locker codes."
                value={form.storageRef}
                onChange={(e) => set("storageRef", e.target.value)}
                maxLength={200}
                error={errors.storage_reference}
              />
            )}
          </fieldset>
        )}

        {step === 5 && reportId && (
          <>
            <AiSuggestions
              reportId={reportId}
              current={suggestionValues}
              onUse={(field, value) => set(field, field === "category" ? (value as Category) : value)}
            />
            <CategorySelect value={form.category} onChange={(c) => set("category", c)} error={errors.category} />
            <Field id="review_item_label" label="What is it?" value={form.item_label} onChange={(e) => set("item_label", e.target.value)} maxLength={120} error={errors.item_label} />
            <div className="grid gap-4 sm:grid-cols-3">
              <Field id="review_brand" label="Brand" value={form.brand} onChange={(e) => set("brand", e.target.value)} maxLength={80} />
              <Field id="review_model" label="Model" value={form.model} onChange={(e) => set("model", e.target.value)} maxLength={80} />
              <Field id="review_colour" label="Main colour" value={form.colour} onChange={(e) => set("colour", e.target.value)} maxLength={40} />
            </div>
          </>
        )}

        {step === 6 && <Summary form={form} isStaff={isStaff} />}

        <div className="flex flex-wrap justify-between gap-2 border-t pt-4">
          {step > 0 ? (
            <Button type="button" variant="outline" onClick={() => setStep((s) => s - 1)} disabled={busy}>
              Back
            </Button>
          ) : (
            <Button asChild variant="ghost">
              <Link href={isEdit && reportId ? `/reports/${reportId}` : "/dashboard"}>Cancel</Link>
            </Button>
          )}
          <Button type="submit" disabled={busy}>
            {step < STEPS.length - 1
              ? save.isPending
                ? "Saving…"
                : step === DRAFT_STEP || (reportId && step === 4)
                  ? "Save and continue"
                  : "Continue"
              : finish.isPending
                ? "Saving…"
                : isEdit
                  ? "Save changes"
                  : "Submit report"}
          </Button>
        </div>
      </form>
      {reportId && !isEdit && (
        <p className="text-center text-sm text-muted-foreground">Your draft is saved. You can come back to it from My reports.</p>
      )}
    </div>
  );
}

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case "NOT_A_MEMBER":
        return "Only that organisation's staff can record items it holds. Choose “I handed it to an organisation” instead.";
      case "INVALID_LOCATION":
        return "That location doesn't belong to the organisation. Choose again.";
      case "FORBIDDEN":
        return "You can't make that change to this report.";
    }
    if (error.status === 409) return "This report can no longer be changed. It may have been submitted or closed.";
  }
  return "We couldn't save your report. Your details are still here. Try again.";
}

function PublicWarning() {
  return (
    <Alert>
      <ShieldAlert aria-hidden />
      <AlertTitle>Keep it safe to share</AlertTitle>
      <AlertDescription>
        Don&apos;t include where the item is stored, access or locker codes, or identifying details such as names or
        card numbers. You can add identifying details privately later.
      </AlertDescription>
    </Alert>
  );
}

function CustodyStep({
  form,
  set,
  errors,
  memberships,
  locked,
}: {
  form: FoundForm;
  set: <K extends keyof FoundForm>(key: K, value: FoundForm[K]) => void;
  errors: Record<string, string>;
  memberships: Membership[];
  locked: boolean;
}) {
  if (locked) {
    return (
      <div className="grid gap-3">
        <p>
          <strong>{form.custody ? custodyLabel[form.custody] : "Not set"}</strong>
        </p>
        {isOrgCustody(form.custody) && <ListedLocation orgId={form.orgId} locationId={form.locationId} />}
        <p className="text-sm text-muted-foreground">
          This can&apos;t be changed after the draft is saved. If it&apos;s wrong, withdraw this draft and start a new report.
        </p>
      </div>
    );
  }

  const options: { value: Custody; label: string; body: string; icon: typeof Hand }[] = [
    { value: "finder_holds", label: "I have the item", body: "You're keeping it safe until the owner is verified.", icon: Hand },
    {
      value: "transferred",
      label: "I handed it to an organisation",
      body: "For example an airport desk, hotel reception or venue lost property.",
      icon: Building2,
    },
  ];
  if (memberships.length) {
    options.push({
      value: "organisation_holds",
      label: "Our organisation is holding it",
      body: "Staff recording an item your organisation has in custody.",
      icon: Building2,
    });
  }

  return (
    <div className="grid gap-5">
      <fieldset className="grid gap-2" aria-describedby={errors.custody ? "custody-error" : undefined}>
        <legend className="mb-1 text-sm font-medium">Who has the item now?</legend>
        {options.map((o) => (
          <label
            key={o.value}
            className={cn(
              "flex cursor-pointer gap-3 rounded-md border p-3 has-[:checked]:border-primary has-[:checked]:bg-accent/50 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
            )}
          >
            <input
              type="radio"
              name="custody"
              value={o.value}
              checked={form.custody === o.value}
              onChange={() => {
                set("custody", o.value);
                set("orgId", "");
                set("locationId", "");
              }}
              className="mt-1 accent-[var(--primary)]"
            />
            <o.icon className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
            <span>
              <span className="block font-medium">{o.label}</span>
              <span className="block text-sm text-muted-foreground">{o.body}</span>
            </span>
          </label>
        ))}
        {errors.custody && (
          <p id="custody-error" className="text-sm text-destructive">
            {errors.custody}
          </p>
        )}
      </fieldset>

      {isOrgCustody(form.custody) && (
        <OrgAndLocation
          custody={form.custody as Custody}
          orgId={form.orgId}
          locationId={form.locationId}
          memberships={memberships}
          onOrg={(id) => {
            set("orgId", id);
            const m = memberships.find((x) => x.organisation_id === id);
            set("locationId", form.custody === "organisation_holds" && m?.location_ids.length === 1 ? m.location_ids[0] : "");
          }}
          onLocation={(id) => set("locationId", id)}
          errors={errors}
        />
      )}
    </div>
  );
}

function OrgAndLocation({
  custody,
  orgId,
  locationId,
  memberships,
  onOrg,
  onLocation,
  errors,
}: {
  custody: Custody;
  orgId: string;
  locationId: string;
  memberships: Membership[];
  onOrg: (id: string) => void;
  onLocation: (id: string) => void;
  errors: Record<string, string>;
}) {
  const staffPath = custody === "organisation_holds";
  // Staff record items for their own organisations; finders can hand items to any participating one.
  const orgs = useQuery({
    queryKey: ["organisations"],
    queryFn: () => unwrap(api.GET("/api/v1/organisations", { params: { query: { limit: 100 } } })),
    enabled: !staffPath,
  });
  const orgOptions = staffPath
    ? memberships.map((m) => ({ id: m.organisation_id, name: m.organisation_name }))
    : (orgs.data ?? []).map((o) => ({ id: o.id, name: o.name }));

  const locations = useQuery({
    queryKey: ["org", orgId, "locations"],
    queryFn: () => unwrap(api.GET("/api/v1/organisations/{org_id}/locations", { params: { path: { org_id: orgId } } })),
    enabled: !!orgId,
  });
  const assigned = memberships.find((m) => m.organisation_id === orgId)?.location_ids ?? [];
  const locationOptions = (locations.data ?? []).filter((l) => !staffPath || !assigned.length || assigned.includes(l.id));

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <FieldShell id="org" label="Organisation" error={errors.organisation_id}>
        <Select value={orgId || undefined} onValueChange={onOrg}>
          <SelectTrigger id="org" className="w-full" aria-invalid={errors.organisation_id ? true : undefined} aria-describedby={describedBy("org", undefined, errors.organisation_id)}>
            <SelectValue placeholder={orgs.isPending && !staffPath ? "Loading…" : "Choose an organisation"} />
          </SelectTrigger>
          <SelectContent>
            {orgOptions.map((o) => (
              <SelectItem key={o.id} value={o.id}>
                {o.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </FieldShell>
      <FieldShell id="location" label="Location" error={errors.location_id}>
        <Select value={locationId || undefined} onValueChange={onLocation} disabled={!orgId}>
          <SelectTrigger id="location" className="w-full" aria-invalid={errors.location_id ? true : undefined} aria-describedby={describedBy("location", undefined, errors.location_id)}>
            <SelectValue placeholder={orgId ? "Choose a location" : "Choose an organisation first"} />
          </SelectTrigger>
          <SelectContent>
            {locationOptions.map((l) => (
              <SelectItem key={l.id} value={l.id}>
                {l.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </FieldShell>
      {(orgs.isError || locations.isError) && (
        <p className="text-sm text-destructive sm:col-span-2" role="alert">
          We couldn&apos;t load the list. Go back and try again.
        </p>
      )}
    </div>
  );
}

function ListedLocation({ orgId, locationId }: { orgId: string; locationId: string }) {
  const locations = useQuery({
    queryKey: ["org", orgId, "locations"],
    queryFn: () => unwrap(api.GET("/api/v1/organisations/{org_id}/locations", { params: { path: { org_id: orgId } } })),
    enabled: !!orgId,
  });
  const loc = locations.data?.find((l) => l.id === locationId);
  return (
    <p className="rounded-md bg-muted p-3 text-sm">
      Listed at <strong>{loc?.name ?? "the organisation's location"}</strong>. The listing shows the organisation&apos;s
      location, never where the item is stored.
    </p>
  );
}

function Summary({ form, isStaff }: { form: FoundForm; isStaff: boolean }) {
  const privateEntries = PRIVATE_FIELDS.filter((f) => form.private[f.key]?.trim());
  return (
    <div className="grid gap-4">
      <section className="grid gap-2">
        <h3 className="flex items-center gap-1.5 font-medium">
          <Eye className="size-4" aria-hidden /> Can be shown to possible owners
        </h3>
        <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[10rem_1fr]">
          <dt className="text-muted-foreground">Item</dt>
          <dd>
            {form.item_label} · {form.category && categoryLabel[form.category]}
          </dd>
          <dt className="text-muted-foreground">Description</dt>
          <dd className="whitespace-pre-line">{form.description}</dd>
          {(form.brand || form.model || form.colour) && (
            <>
              <dt className="text-muted-foreground">Visible details</dt>
              <dd>{[form.brand, form.model, form.colour].filter(Boolean).join(" · ")}</dd>
            </>
          )}
          <dt className="text-muted-foreground">Found</dt>
          <dd>
            {form.custody === "finder_holds" ? form.place : "At the organisation's location"} ·{" "}
            {form.foundAt && new Date(form.foundAt).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
          </dd>
          <dt className="text-muted-foreground">Photos</dt>
          <dd>{form.images.length || "None"}</dd>
        </dl>
      </section>
      <section className="grid gap-2 rounded-md border border-dashed p-4">
        <h3 className="flex items-center gap-1.5 font-medium">
          <EyeOff className="size-4" aria-hidden /> Private: only you and authorised reviewers
        </h3>
        {privateEntries.length || (isStaff && form.storageRef.trim()) ? (
          <ul className="list-disc pl-5 text-sm">
            {privateEntries.map((f) => (
              <li key={f.key}>{f.label}</li>
            ))}
            {isStaff && form.storageRef.trim() && <li>Storage reference (your organisation only)</li>}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No private details added.</p>
        )}
      </section>
      <p className="text-sm text-muted-foreground">
        After you submit, we look for lost reports that may match. Possible owners are told a match exists, never where
        the item is kept.
      </p>
    </div>
  );
}
