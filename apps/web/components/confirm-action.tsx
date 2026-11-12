"use client";

import { useState, type ReactNode } from "react";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";

/**
 * A button that asks for confirmation before an irreversible action (docs/02 §2.5).
 * `children` can hold extra inputs (e.g. a required reason); `canConfirm` gates the confirm button.
 * The dialog stays open until `onConfirm` resolves, so errors can be shown inside it.
 */
export function ConfirmAction({
  trigger,
  triggerVariant = "outline",
  title,
  description,
  confirmLabel,
  pendingLabel = "Working…",
  destructive,
  onConfirm,
  pending,
  canConfirm = true,
  error,
  children,
}: {
  trigger: ReactNode;
  triggerVariant?: "default" | "outline" | "ghost" | "secondary" | "destructive" | "destructive-outline";
  title: string;
  description: ReactNode;
  confirmLabel: string;
  pendingLabel?: string;
  destructive?: boolean;
  onConfirm: () => Promise<unknown>;
  pending?: boolean;
  canConfirm?: boolean;
  error?: string | null;
  children?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <AlertDialog open={open} onOpenChange={(o) => !pending && setOpen(o)}>
      <AlertDialogTrigger asChild>
        <Button variant={triggerVariant}>{trigger}</Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        {children}
        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>Cancel</AlertDialogCancel>
          <Button
            variant={destructive ? "destructive" : "default"}
            disabled={pending || !canConfirm}
            onClick={async () => {
              try {
                await onConfirm();
                setOpen(false);
              } catch {
                // Keep the dialog open; the caller shows `error`.
              }
            }}
          >
            {pending ? pendingLabel : confirmLabel}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
