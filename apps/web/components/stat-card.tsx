import Link from "next/link";
import { ArrowUpRight, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/** Summary number. With `href` the whole card is a link and says so on hover and focus. */
export function StatCard({
  label,
  value,
  icon: Icon,
  note,
  href,
}: {
  label: string;
  value: number;
  icon: LucideIcon;
  note?: string;
  href?: string;
}) {
  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-accent text-brand" aria-hidden>
          <Icon className="size-4" />
        </span>
      </div>
      <p className="text-4xl leading-none font-bold tabular-nums">{value}</p>
      {note && <p className="text-sm text-muted-foreground">{note}</p>}
      {href && (
        <span className="mt-auto inline-flex items-center gap-1 text-sm font-medium text-brand">
          View <ArrowUpRight className="size-3.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" aria-hidden />
        </span>
      )}
    </>
  );
  const cls = "group flex h-full flex-col gap-3 surface p-5";
  return href ? (
    <Link href={href} data-slot="stat-card" className={cn(cls, "transition-colors hover:border-foreground/40")}>
      {body}
    </Link>
  ) : (
    <div data-slot="stat-card" className={cls}>
      {body}
    </div>
  );
}
