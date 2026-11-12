"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { BrandLogo } from "@/components/brand-logo";

export type NavItem = { href: string; label: string };

/** Header for signed-in areas. `context` sits beside the wordmark (e.g. the org switcher). */
export function AppHeader({ nav, context, actions }: { nav: NavItem[]; context?: ReactNode; actions?: ReactNode }) {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-20 border-b bg-card/95 backdrop-blur">
      <a
        href="#main"
        className="sr-only z-30 rounded-md bg-primary px-4 py-2 font-semibold text-primary-foreground focus:not-sr-only focus:absolute focus:top-2 focus:left-2"
      >
        Skip to content
      </a>
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-1 px-4 pt-3">
        <BrandLogo className="h-7 md:h-8" priority />
        {context}
        <div className="ml-auto">{actions}</div>
        {/* On phones the nav scrolls sideways; the fade on the right shows there's more. */}
        <nav
          aria-label="Main"
          className="-mx-4 flex w-[calc(100%+2rem)] gap-1 overflow-x-auto px-3 [mask-image:linear-gradient(to_right,black_85%,transparent)] md:mx-0 md:w-full md:px-0 md:[mask-image:none]"
        >
          {nav.map((item) => {
            const nested = nav.some((other) => other !== item && other.href.startsWith(`${item.href}/`));
            const active = pathname === item.href || (!nested && pathname.startsWith(`${item.href}/`));
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative flex h-11 items-center px-3 text-sm font-medium whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground",
                  "after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:rounded-full after:bg-transparent",
                  active && "font-semibold text-foreground after:bg-brand",
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
