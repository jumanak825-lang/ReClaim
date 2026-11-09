"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type NavItem = { href: string; label: string };

/** Header for signed-in areas. `context` sits beside the wordmark (e.g. the org switcher). */
export function AppHeader({ nav, context, actions }: { nav: NavItem[]; context?: ReactNode; actions?: ReactNode }) {
  const pathname = usePathname();
  return (
    <header className="border-b bg-card">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
        <Link href="/" className="text-lg font-semibold tracking-tight">
          Reclaim
        </Link>
        {context}
        <div className="ml-auto">{actions}</div>
        <nav aria-label="Main" className="-mx-1 flex w-full gap-1 overflow-x-auto sm:order-none">
          {nav.map((item) => {
            const nested = nav.some((other) => other !== item && other.href.startsWith(`${item.href}/`));
            const active = pathname === item.href || (!nested && pathname.startsWith(`${item.href}/`));
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm whitespace-nowrap text-muted-foreground hover:bg-muted hover:text-foreground",
                  active && "bg-accent font-medium text-accent-foreground",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
