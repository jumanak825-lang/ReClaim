import type { Me } from "@/lib/api/me";

type Related = { type: string; related_entity_type: string | null; related_entity_id: string | null };

/**
 * Where a notification (or activity item) leads. Staff-facing ones open in the organisation portal;
 * the API still decides what each viewer may see on the target page.
 */
export function notificationHref(n: Related, me: Me | undefined): string | null {
  const id = n.related_entity_id;
  if (!id || !n.related_entity_type) return null;
  const orgSlug = me?.memberships[0]?.organisation_slug;
  switch (n.related_entity_type) {
    case "report":
      return `/reports/${id}`;
    case "match":
      return `/matches/${id}`;
    case "claim":
      return n.type === "claim.new_for_review" && orgSlug ? `/org/${orgSlug}/claims/${id}` : `/claims/${id}`;
    case "recovery":
    case "payment":
      // Staff get recovery notifications for items their organisation holds; claimants for their own.
      return orgSlug && n.type === "payment.captured" && n.related_entity_type === "recovery"
        ? `/org/${orgSlug}/recoveries/${id}`
        : `/recoveries/${id}`;
    default:
      return null;
  }
}

