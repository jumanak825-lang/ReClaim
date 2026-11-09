"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { createContext, use, type ReactNode } from "react";
import { Building2, ChevronDown } from "lucide-react";
import { useMe, type Membership } from "@/lib/api/me";
import { AppHeader, type NavItem } from "@/components/app-header";
import { HeaderActions } from "@/components/header-actions";
import { PermissionDenied } from "@/components/states";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const OrgContext = createContext<Membership | null>(null);

/** The membership for the organisation in the URL. Only usable inside OrgShell. */
export function useOrg(): Membership {
  const m = use(OrgContext);
  if (!m) throw new Error("useOrg must be used inside OrgShell");
  return m;
}

/**
 * Resolves /org/[orgSlug] against the user's memberships. The UI check only decides what to
 * show: the API still enforces membership on every organisation request.
 */
export function OrgShell({ children }: { children: ReactNode }) {
  const { orgSlug } = useParams<{ orgSlug: string }>();
  const { data: me } = useMe();
  const membership = me?.memberships.find((m) => m.organisation_slug === orgSlug);

  if (!me || !membership) {
    return (
      <PermissionDenied
        message="You aren't a member of this organisation."
        action={
          <Button asChild variant="outline">
            <Link href="/dashboard">Go to your dashboard</Link>
          </Button>
        }
      />
    );
  }

  // Items are added as their pages land (docs/02 §2.3).
  // Hiding items is convenience only; the API enforces each role on every request.
  const canAudit = ["reviewer", "manager", "admin"].includes(membership.role);
  const canManage = ["manager", "admin"].includes(membership.role);
  const nav: NavItem[] = [
    { href: `/org/${orgSlug}`, label: "Overview" },
    { href: `/org/${orgSlug}/operations`, label: "Operations" },
    { href: `/org/${orgSlug}/claims`, label: "Claims" },
    ...(canAudit ? [{ href: `/org/${orgSlug}/audit`, label: "Audit log" }] : []),
    ...(canManage ? [{ href: `/org/${orgSlug}/integrations`, label: "Integrations" }] : []),
  ];

  return (
    <OrgContext value={membership}>
      <AppHeader nav={nav} context={<OrgSwitcher current={membership} all={me.memberships} />} actions={<HeaderActions />} />
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8">{children}</main>
    </OrgContext>
  );
}

function OrgSwitcher({ current, all }: { current: Membership; all: Membership[] }) {
  const label = (
    <>
      <Building2 className="size-4" aria-hidden />
      <span className="truncate">{current.organisation_name}</span>
    </>
  );
  if (all.length < 2) {
    return <span className="flex max-w-56 items-center gap-1.5 text-sm text-muted-foreground">{label}</span>;
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="max-w-56" aria-label={`Organisation: ${current.organisation_name}. Switch organisation`}>
          {label}
          <ChevronDown className="size-4" aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        <DropdownMenuLabel>Switch organisation</DropdownMenuLabel>
        {all.map((m) => (
          <DropdownMenuItem key={m.organisation_id} asChild>
            <Link href={`/org/${m.organisation_slug}`} aria-current={m === current ? "true" : undefined}>
              {m.organisation_name}
            </Link>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
