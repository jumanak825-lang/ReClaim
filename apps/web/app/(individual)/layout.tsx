import { Suspense } from "react";
import { AuthGate } from "@/components/auth/auth-gate";
import { UserMenu } from "@/components/auth/user-menu";
import { AppHeader, type NavItem } from "@/components/app-header";
import { LoadingState } from "@/components/states";

// Items are added as their pages land (docs/02 §2.3).
const nav: NavItem[] = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/report/lost", label: "Report lost" },
  { href: "/report/found", label: "Report found" },
  { href: "/reports", label: "My reports" },
  { href: "/matches", label: "Matches" },
  { href: "/claims", label: "My claims" },
];

export default function IndividualLayout({ children }: LayoutProps<"/">) {
  return (
    <Suspense fallback={<LoadingState />}>
      <AuthGate>
        <AppHeader nav={nav} actions={<UserMenu />} />
        <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8">{children}</main>
      </AuthGate>
    </Suspense>
  );
}
