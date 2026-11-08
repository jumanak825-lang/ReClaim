import { Suspense } from "react";
import { AuthGate } from "@/components/auth/auth-gate";
import { OrgShell } from "@/components/organisation/org-shell";
import { LoadingState } from "@/components/states";

export default function OrganisationLayout({ children }: LayoutProps<"/org/[orgSlug]">) {
  return (
    <Suspense fallback={<LoadingState />}>
      <AuthGate>
        <OrgShell>{children}</OrgShell>
      </AuthGate>
    </Suspense>
  );
}
