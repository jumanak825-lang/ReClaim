import { AlertTriangle, CheckCircle2, Clock, XCircle } from "lucide-react";
import type { Schemas } from "@/lib/api/client";
import { claimStatusLabel } from "@/lib/labels";
import { Badge } from "@/components/ui/badge";

export function ClaimStatusBadge({ status }: { status: Schemas["ClaimOut"]["status"] }) {
  const label = claimStatusLabel[status];
  switch (status) {
    case "pending":
      return (
        <Badge className="bg-warning text-warning-foreground">
          <Clock aria-hidden /> {label}
        </Badge>
      );
    case "escalated":
      return (
        <Badge className="bg-warning text-warning-foreground">
          <AlertTriangle aria-hidden /> {label}
        </Badge>
      );
    case "approved":
      return (
        <Badge className="bg-success text-success-foreground">
          <CheckCircle2 aria-hidden /> {label}
        </Badge>
      );
    default:
      return (
        <Badge variant="secondary">
          <XCircle aria-hidden /> {label}
        </Badge>
      );
  }
}
