import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowLeft, FlaskConical, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/** Shared page building blocks so every screen has the same header, panels and empty states. */

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  back,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  back?: { href: string; label: string };
}) {
  return (
    <div className="grid gap-4">
      {back && <BackLink href={back.href}>{back.label}</BackLink>}
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div className="grid min-w-0 gap-2">
          {eyebrow && <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">{eyebrow}</div>}
          <h1 className="text-[1.75rem] leading-tight font-bold md:text-[2rem]">{title}</h1>
          {description && <p className="max-w-2xl text-muted-foreground">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}

export function BackLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      className="inline-flex w-fit items-center gap-1.5 rounded-md text-sm font-medium text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="size-4" aria-hidden />
      {children}
    </Link>
  );
}


export function EmptyState({
  icon: Icon,
  title,
  children,
  action,
  className,
}: {
  icon: LucideIcon;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("grid justify-items-center gap-3 surface px-6 py-10 text-center", className)}>
      <span className="flex size-12 items-center justify-center rounded-full bg-accent text-brand" aria-hidden>
        <Icon className="size-5" />
      </span>
      <h2 className="text-lg font-semibold">{title}</h2>
      {children && <div className="max-w-md text-muted-foreground">{children}</div>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}

/** Marks anything simulated or sandboxed. Always visible: these labels are part of the demo's honesty. */
export function SimBadge({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex h-6 w-fit shrink-0 items-center gap-1 rounded-full border border-dashed border-foreground/40 bg-card px-2.5 text-xs font-semibold whitespace-nowrap text-foreground">
      <FlaskConical className="size-3" aria-hidden />
      {children}
    </span>
  );
}

/** Filter tabs as toggle buttons (aria-pressed), drawn as one segmented control. */
export function SegmentedControl<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex w-fit max-w-full gap-1 overflow-x-auto surface p-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className="h-9 rounded-md px-4 text-sm font-semibold whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground aria-pressed:bg-primary aria-pressed:text-primary-foreground"
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
