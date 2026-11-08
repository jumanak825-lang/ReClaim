import { ApiError } from "./client";

/**
 * Map a VALIDATION_ERROR's details.fields[] ({ loc: ["body", "email"], message }) to
 * { email: message } so forms can show errors next to the right input.
 */
export function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || error.code !== "VALIDATION_ERROR") return {};
  const fields = (error.details.fields ?? []) as { loc: string[]; message: string }[];
  const out: Record<string, string> = {};
  for (const f of fields) {
    const name = f.loc[f.loc.length - 1];
    if (name && !out[name]) out[name] = f.message;
  }
  return out;
}
