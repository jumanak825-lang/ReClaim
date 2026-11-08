import type { LucideIcon } from "lucide-react";

export function StatCard({ label, value, icon: Icon, note }: { label: string; value: number; icon: LucideIcon; note?: string }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">{label}</p>
        <Icon className="size-4 text-primary" aria-hidden />
      </div>
      <p className="mt-2 text-3xl font-semibold tabular-nums">{value}</p>
      {note && <p className="mt-1 text-sm text-muted-foreground">{note}</p>}
    </div>
  );
}
