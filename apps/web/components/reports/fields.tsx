"use client";

import { useId, type ReactNode } from "react";
import type { Schemas } from "@/lib/api/client";
import { categoryLabel } from "@/lib/labels";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

export type Category = Schemas["ReportOut"]["category"];
export const categories = Object.keys(categoryLabel) as Category[];

/** Wraps any control with a label, hint and an error linked for screen readers. */
export function FieldShell({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {hint && (
        <p id={`${id}-hint`} className="text-sm text-muted-foreground">
          {hint}
        </p>
      )}
      {children}
      {error && (
        <p id={`${id}-error`} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

export function describedBy(id: string, hint?: string, error?: string) {
  return [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(" ") || undefined;
}

export function CategorySelect({
  value,
  onChange,
  error,
}: {
  value: Category | "";
  onChange: (c: Category) => void;
  error?: string;
}) {
  const id = useId();
  return (
    <FieldShell id={id} label="Category" error={error}>
      <Select value={value || undefined} onValueChange={(v) => onChange(v as Category)}>
        <SelectTrigger id={id} className="w-full" aria-invalid={error ? true : undefined} aria-describedby={describedBy(id, undefined, error)}>
          <SelectValue placeholder="Choose a category" />
        </SelectTrigger>
        <SelectContent>
          {categories.map((c) => (
            <SelectItem key={c} value={c}>
              {categoryLabel[c]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </FieldShell>
  );
}

export function TextArea({
  label,
  hint,
  error,
  value,
  onChange,
  maxLength,
  required,
}: {
  label: string;
  hint?: string;
  error?: string;
  value: string;
  onChange: (v: string) => void;
  maxLength: number;
  required?: boolean;
}) {
  const id = useId();
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <Textarea
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        maxLength={maxLength}
        required={required}
        rows={4}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
      />
    </FieldShell>
  );
}
