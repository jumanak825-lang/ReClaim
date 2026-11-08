import { CheckCircle2, Clock, FileEdit, Loader2, XCircle } from "lucide-react";
import type { Schemas } from "@/lib/api/client";
import { reportStatusLabel } from "@/lib/labels";
import { Badge } from "@/components/ui/badge";

/** Status shown with text and an icon, not colour alone (docs/02 §2.7). */
export function ReportStatusBadge({ status }: { status: Schemas["ReportOut"]["status"] }) {
  const label = reportStatusLabel[status];
  switch (status) {
    case "draft":
      return (
        <Badge variant="outline">
          <FileEdit aria-hidden /> {label}
        </Badge>
      );
    case "submitted":
    case "processing":
      return (
        <Badge className="bg-warning text-warning-foreground">
          <Loader2 className="animate-spin" aria-hidden /> {label}
        </Badge>
      );
    case "active":
      return (
        <Badge>
          <Clock aria-hidden /> {label}
        </Badge>
      );
    case "resolved":
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
