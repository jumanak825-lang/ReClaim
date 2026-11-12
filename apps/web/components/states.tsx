"use client";

import { AlertTriangle, Loader2, ShieldX } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";

/** Shared page states required on every data-driven screen (docs/02 §2.5). */

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex flex-1 items-center justify-center p-8 text-muted-foreground" role="status">
      <Loader2 className="mr-2 size-4 animate-spin" aria-hidden />
      {label}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message = "We couldn't load this. Check your connection and try again.",
  onRetry,
  retrying,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
  retrying?: boolean;
}) {
  return (
    <StateBox icon={<AlertTriangle className="size-5 text-destructive" aria-hidden />} tint="bg-destructive/10" title={title} role="alert">
      <p className="text-muted-foreground">{message}</p>
      {onRetry && (
        <Button variant="outline" onClick={onRetry} disabled={retrying} className="mt-4">
          {retrying ? "Retrying…" : "Try again"}
        </Button>
      )}
    </StateBox>
  );
}

export function PermissionDenied({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <StateBox icon={<ShieldX className="size-5 text-foreground" aria-hidden />} tint="bg-secondary" title="You don't have access">
      <p className="text-muted-foreground">{message}</p>
      {action && <div className="mt-4">{action}</div>}
    </StateBox>
  );
}

function StateBox({
  icon,
  tint,
  title,
  role,
  children,
}: {
  icon: ReactNode;
  tint: string;
  title: string;
  role?: string;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto flex max-w-md flex-1 flex-col items-center justify-center p-8 text-center" role={role}>
      <span className={`flex size-12 items-center justify-center rounded-full ${tint}`}>{icon}</span>
      <h2 className="mt-4 text-lg font-semibold">{title}</h2>
      <div className="mt-1">{children}</div>
    </div>
  );
}
