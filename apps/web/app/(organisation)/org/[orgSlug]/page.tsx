"use client";

import { useOrg } from "@/components/organisation/org-shell";

// Shell only. Overview cards, priority queue and location selector (docs/02 Screen 10) come next phase.
export default function OrganisationOverviewPage() {
  const org = useOrg();
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">{org.organisation_name}</h1>
      <p className="mt-1 text-muted-foreground">
        Signed in as <span className="capitalize">{org.role}</span>
      </p>
    </div>
  );
}
