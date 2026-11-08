"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff } from "lucide-react";
import { api, ApiError, unwrap, type Schemas } from "@/lib/api/client";
import { fieldErrors } from "@/lib/api/form-errors";
import type { Image } from "@/lib/api/uploads";
import { toLocalInput } from "@/lib/datetime";
import { categoryLabel } from "@/lib/labels";
import { Field } from "@/components/auth/field";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { AiSuggestions, type SuggestionField } from "./ai-suggestions";
import { CategorySelect, TextArea, type Category } from "./fields";
import { ImageUploader } from "./image-uploader";
import { Stepper } from "./stepper";

type Report = Schemas["ReportOut"];

const STEPS = ["Item", "Where and when", "Photos and private details", "Review suggestions", "Confirm"];

// Private keys the wizard offers. Never shown publicly (docs/08 §8.5).
const PRIVATE_FIELDS = [
  { key: "distinctive_marks", label: "Distinctive marks, stickers or damage", hint: "Only you and authorised reviewers see this." },
  { key: "serial_number", label: "Serial number", hint: "Optional. Leave blank if you don't know it." },
  { key: "other_private", label: "Anything else only the owner would know", hint: "For example, what was inside or attached." },
] as const;

export type LostForm = {
  category: Category | "";
  item_label: string;
  description: string;
  brand: string;
  model: string;
  colour: string;
  notSure: boolean;
  lostStart: string; // datetime-local, in the user's timezone
  lostEnd: string;
  location: string;
  images: Image[];
  private: Record<string, string>;
};

const empty: LostForm = {
  category: "",
  item_label: "",
  description: "",
  brand: "",
  model: "",
  colour: "",
  notSure: false,
  lostStart: "",
  lostEnd: "",
  location: "",
  images: [],
  private: {},
};

function fromReport(r: Report): LostForm {
  return {
    category: r.category,
    item_label: r.item_label,
    description: r.description,
    brand: r.brand ?? "",
    model: r.model ?? "",
    colour: r.attributes_public.colour ?? "",
    notSure: !r.lost_at_start,
    lostStart: toLocalInput(r.lost_at_start),
    lostEnd: toLocalInput(r.lost_at_end),
    location: r.location_label,
    images: r.images,
    private: { ...(r.attributes_private ?? {}) },
  };
}

function toPayload(f: LostForm) {
  const start = !f.notSure && f.lostStart ? new Date(f.lostStart).toISOString() : null;
  const end = !f.notSure && f.lostEnd ? new Date(f.lostEnd).toISOString() : null;
  const privateAttrs: Record<string, string> = Object.fromEntries(
    Object.entries(f.private)
      .map(([k, v]) => [k, v.trim()] as const)
      .filter(([, v]) => v),
  );
  const publicAttrs: Record<string, string> = f.colour.trim() ? { colour: f.colour.trim().toLowerCase() } : {};
  // category/item_label/description/location are always present here, so nothing required is sent as null.
  return {
    category: f.category as Category,
    item_label: f.item_label.trim(),
    description: f.description.trim(),
    brand: f.brand.trim() || null,
    model: f.model.trim() || null,
    lost_at_start: start,
    lost_at_end: end,
    last_location: { label: f.location.trim() },
    attributes_public: publicAttrs,
    attributes_private: privateAttrs,
    image_ids: f.images.map((i) => i.id),
  };
}

function validate(step: number, f: LostForm): Record<string, string> {
  const e: Record<string, string> = {};
  if (step === 0) {
    if (!f.category) e.category = "Choose a category.";
    if (!f.item_label.trim()) e.item_label = "Say what the item is.";
    if (!f.description.trim()) e.description = "Describe the item.";
  }
  if (step === 1) {
    if (!f.location.trim()) e.label = "Add where you last had it. An approximate place is fine.";
    if (!f.notSure && !f.lostStart) e.lost_at_start = "Add an approximate time, or tick “I'm not sure”.";
    if (!f.notSure && f.lostStart && f.lostEnd && f.lostEnd < f.lostStart) e.lost_at_end = "This must be after the first time.";
  }
  return e;
}

/**
 * Lost report wizard (docs/02 Screen 4). The draft is created on leaving step 3 so photos and
 * details survive a refresh; `?id=` resumes it. With an already-submitted report it edits instead.
 */
export function LostWizard({ existing, initialStep = 0 }: { existing?: Report; initialStep?: number }) {
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const [step, setStep] = useState(Math.min(Math.max(initialStep, 0), existing ? STEPS.length - 1 : 0));
  const [form, setForm] = useState<LostForm>(existing ? fromReport(existing) : empty);
  // A new draft remounts the wizard through the URL (?id=), so the id never changes in here.
  const reportId = existing?.id ?? null;
  const [clientErrors, setClientErrors] = useState<Record<string, string>>({});
  const isEdit = !!existing && existing.status !== "draft";
  const headingRef = useRef<HTMLHeadingElement>(null);
  const firstRender = useRef(true);

  useEffect(() => {
    // Keep the step in the URL once a draft exists, so a refresh resumes at the same place.
    if (reportId) router.replace(`${pathname}?id=${reportId}&step=${step + 1}`, { scroll: false });
    // Move focus to the new step's heading for keyboard and screen-reader users.
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    headingRef.current?.focus();
  }, [step, reportId, router, pathname]);

  const set = <K extends keyof LostForm>(key: K, value: LostForm[K]) => setForm((f) => ({ ...f, [key]: value }));

  const save = useMutation({
    mutationFn: async () => {
      const body = toPayload(form);
      if (!reportId) return unwrap(api.POST("/api/v1/reports/lost", { body: { ...body, as_draft: true } }));
      return unwrap(api.PATCH("/api/v1/reports/{report_id}", { params: { path: { report_id: reportId } }, body }));
    },
    // Cache it so the resumed wizard renders from it without a loading flash.
    onSuccess: (r) => queryClient.setQueryData(["reports", r.id], r),
  });

  const finish = useMutation({
    mutationFn: async () => {
      const id = reportId!;
      const body = toPayload(form);
      const saved = await unwrap(api.PATCH("/api/v1/reports/{report_id}", { params: { path: { report_id: id } }, body }));
      if (isEdit) return saved;
      return unwrap(api.POST("/api/v1/reports/{report_id}/submit", { params: { path: { report_id: id } } }));
    },
    onSuccess: async (r) => {
      queryClient.setQueryData(["reports", r.id], r);
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      await queryClient.invalidateQueries({ queryKey: ["reports", "mine"] });
      router.push(`/reports/${r.id}`);
    },
  });

  const serverErrors = { ...fieldErrors(save.error), ...fieldErrors(finish.error) };
  const errors = { ...serverErrors, ...clientErrors };
  const failure = save.error ?? finish.error;
  const failureMessage =
    failure && !Object.keys(serverErrors).length
      ? failure instanceof ApiError && failure.status === 409
        ? "This report can no longer be changed. It may have been submitted or closed."
        : "We couldn't save your report. Your details are still here. Try again."
      : null;

  async function next() {
    const e = validate(step, form);
    setClientErrors(e);
    if (Object.keys(e).length) return;
    if (step === 2) {
      let saved;
      try {
        saved = await save.mutateAsync();
      } catch {
        return;
      }
      if (!reportId) {
        // First save created the draft: continue at step 4 as a resumable draft.
        router.replace(`${pathname}?id=${saved.id}&step=4`, { scroll: false });
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
        <h1 className="text-2xl font-semibold tracking-tight">{isEdit ? "Edit your lost report" : "Report something lost"}</h1>
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
            <CategorySelect value={form.category} onChange={(c) => set("category", c)} error={errors.category} />
            <Field
              id="item_label"
              label="What is it?"
              placeholder="e.g. Laptop, backpack, house keys"
              value={form.item_label}
              onChange={(e) => set("item_label", e.target.value)}
              maxLength={120}
              error={errors.item_label}
            />
            <TextArea
              label="Describe it"
              hint="Colour, size, case, stickers you don't mind being seen. Keep identifying details for step 3."
              value={form.description}
              onChange={(v) => set("description", v)}
              maxLength={2000}
              error={errors.description}
            />
            <div className="grid gap-4 sm:grid-cols-3">
              <Field id="brand" label="Brand (if known)" value={form.brand} onChange={(e) => set("brand", e.target.value)} maxLength={80} error={errors.brand} />
              <Field id="model" label="Model (if known)" value={form.model} onChange={(e) => set("model", e.target.value)} maxLength={80} error={errors.model} />
              <Field id="colour" label="Main colour" value={form.colour} onChange={(e) => set("colour", e.target.value)} maxLength={40} />
            </div>
          </>
        )}

        {step === 1 && (
          <>
            <Field
              id="location"
              label="Where did you last have it?"
              hint="A place name is enough, e.g. “Terminal 1, airport” or “Café on King Street”."
              value={form.location}
              onChange={(e) => set("location", e.target.value)}
              maxLength={200}
              error={errors.label}
            />
            <fieldset className="grid gap-3">
              <legend className="mb-1 text-sm font-medium">When did you lose it?</legend>
              <div className="flex items-center gap-2">
                <Checkbox id="not-sure" checked={form.notSure} onCheckedChange={(v) => set("notSure", v === true)} />
                <Label htmlFor="not-sure" className="font-normal">
                  I&apos;m not sure
                </Label>
              </div>
              {!form.notSure && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field
                    id="lost_start"
                    label="Earliest time"
                    type="datetime-local"
                    value={form.lostStart}
                    onChange={(e) => set("lostStart", e.target.value)}
                    error={errors.lost_at_start}
                  />
                  <Field
                    id="lost_end"
                    label="Latest time (optional)"
                    type="datetime-local"
                    value={form.lostEnd}
                    onChange={(e) => set("lostEnd", e.target.value)}
                    error={errors.lost_at_end}
                  />
                </div>
              )}
            </fieldset>
          </>
        )}

        {step === 2 && (
          <>
            <ImageUploader
              label="Photos (optional)"
              hint="A photo of the item or a similar one helps matching. These can be shown to people who may have found it, so avoid photos showing serial numbers or personal documents."
              visibility="public_safe"
              images={form.images}
              onChange={(imgs) => set("images", imgs)}
            />
            <fieldset className="grid gap-4 rounded-md border border-dashed p-4">
              <legend className="flex items-center gap-1.5 px-1 text-sm font-medium">
                <EyeOff className="size-4" aria-hidden /> Private details
              </legend>
              <p className="text-sm text-muted-foreground">
                These are never shown publicly. They help authorised staff check that you are the owner.
              </p>
              {PRIVATE_FIELDS.map((p) => (
                <Field
                  key={p.key}
                  id={`private-${p.key}`}
                  label={p.label}
                  hint={p.hint}
                  value={form.private[p.key] ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, private: { ...f.private, [p.key]: e.target.value } }))}
                  maxLength={300}
                />
              ))}
            </fieldset>
          </>
        )}

        {step === 3 && reportId && (
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

        {step === 4 && <PrivacySummary form={form} />}

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
                : step === 2
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
        <p className="text-center text-sm text-muted-foreground">
          Your draft is saved. You can come back to it from My reports.
        </p>
      )}
    </div>
  );
}

function PrivacySummary({ form }: { form: LostForm }) {
  const p = toPayload(form);
  const when = form.notSure
    ? "Not sure"
    : [form.lostStart, form.lostEnd].filter(Boolean).map((v) => new Date(v).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })).join(" – ");
  const privateEntries = PRIVATE_FIELDS.filter((f) => p.attributes_private[f.key]);
  return (
    <div className="grid gap-4">
      <section className="grid gap-2">
        <h3 className="flex items-center gap-1.5 font-medium">
          <Eye className="size-4" aria-hidden /> Can be shown to possible matches
        </h3>
        <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[10rem_1fr]">
          <dt className="text-muted-foreground">Item</dt>
          <dd>
            {p.item_label} · {categoryLabel[p.category]}
          </dd>
          <dt className="text-muted-foreground">Description</dt>
          <dd className="whitespace-pre-line">{p.description}</dd>
          {(p.brand || p.model) && (
            <>
              <dt className="text-muted-foreground">Brand / model</dt>
              <dd>{[p.brand, p.model].filter(Boolean).join(" ")}</dd>
            </>
          )}
          {form.colour && (
            <>
              <dt className="text-muted-foreground">Colour</dt>
              <dd>{form.colour}</dd>
            </>
          )}
          <dt className="text-muted-foreground">Last seen</dt>
          <dd>{p.last_location.label}</dd>
          <dt className="text-muted-foreground">When</dt>
          <dd>{when}</dd>
          <dt className="text-muted-foreground">Photos</dt>
          <dd>{form.images.length || "None"}</dd>
        </dl>
      </section>
      <section className="grid gap-2 rounded-md border border-dashed p-4">
        <h3 className="flex items-center gap-1.5 font-medium">
          <EyeOff className="size-4" aria-hidden /> Private: only you and authorised reviewers
        </h3>
        {privateEntries.length ? (
          <ul className="list-disc pl-5 text-sm">
            {privateEntries.map((f) => (
              <li key={f.key}>{f.label}</li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No private details added. You can still prove ownership when you make a claim.</p>
        )}
      </section>
      <p className="text-sm text-muted-foreground">
        After you submit, we look for possible matches across participating locations and let you know. A possible
        match is not proof of ownership.
      </p>
    </div>
  );
}
