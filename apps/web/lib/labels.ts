import type { Schemas } from "@/lib/api/client";

/** Human labels for API enums. Keep wording in one place so screens stay consistent. */

export const claimStatusLabel: Record<Schemas["ClaimListItem"]["status"], string> = {
  pending: "Pending review",
  approved: "Approved",
  rejected: "Not approved",
  escalated: "Escalated",
};

export const recoveryStatusLabel: Record<NonNullable<Schemas["CaseRow"]["recovery_status"]>, string> = {
  created: "Created",
  awaiting_payment: "Awaiting payment",
  preparing: "Preparing",
  ready_for_pickup: "Ready for pickup",
  dispatched: "Dispatched",
  in_transit: "In transit",
  received: "Received",
  completed: "Completed",
  cancelled: "Cancelled",
  failed: "Failed",
  disputed: "Disputed",
};

export const priorityLabel: Record<Schemas["CaseRow"]["priority"], string> = {
  high: "High priority",
  medium: "Medium priority",
  low: "Low priority",
};

const relative = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
const units: [Intl.RelativeTimeFormatUnit, number][] = [
  ["day", 86_400_000],
  ["hour", 3_600_000],
  ["minute", 60_000],
];

/** "5 minutes ago", "yesterday". The full local date/time goes in a `title`/`dateTime` alongside. */
export function timeAgo(iso: string): string {
  const diff = new Date(iso).getTime() - Date.now();
  for (const [unit, ms] of units) {
    if (Math.abs(diff) >= ms || unit === "minute") return relative.format(Math.round(diff / ms), unit);
  }
  return "";
}

export function fullDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
