import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Wizard progress as a segmented track: one segment per step (teal done, charcoal current, grey to come).
 * Wider screens label every segment; phones show the current step's name and "Step n of m" instead,
 * because 5 to 7 labels don't fit at 375px.
 */
export function Stepper({ steps, current }: { steps: string[]; current: number }) {
  return (
    <div className="grid gap-3">
      <p className="flex items-baseline justify-between gap-3 text-sm sm:hidden">
        <span className="font-semibold">{steps[current]}</span>
        <span className="shrink-0 text-muted-foreground tabular-nums">
          Step {current + 1} of {steps.length}
        </span>
      </p>
      <ol
        aria-label={`Progress: step ${current + 1} of ${steps.length}`}
        className="grid gap-1.5 sm:gap-2"
        style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }}
      >
        {steps.map((label, i) => {
          const done = i < current;
          const active = i === current;
          return (
            <li key={label} aria-current={active ? "step" : undefined} className="grid content-start gap-2">
              <span
                className={cn(
                  "h-1.5 rounded-full transition-colors",
                  done ? "bg-brand" : active ? "bg-foreground" : "bg-border",
                )}
                aria-hidden
              />
              <span
                className={cn(
                  "hidden items-start gap-1.5 text-xs leading-snug sm:flex",
                  active ? "font-semibold text-foreground" : done ? "text-foreground" : "text-muted-foreground",
                )}
              >
                <span
                  className={cn(
                    "flex size-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold tabular-nums",
                    done ? "bg-brand text-brand-foreground" : active ? "bg-foreground text-background" : "border border-border bg-card",
                  )}
                  aria-hidden
                >
                  {done ? <Check className="size-3" /> : i + 1}
                </span>
                <span className="pt-0.5">
                  {label}
                  {done && <span className="sr-only"> (completed)</span>}
                </span>
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
