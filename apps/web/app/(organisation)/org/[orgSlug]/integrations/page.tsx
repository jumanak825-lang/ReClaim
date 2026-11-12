"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleSlash, Zap } from "lucide-react";
import { api, ApiError, unwrap } from "@/lib/api/client";
import { fullDateTime, humanizeKey } from "@/lib/labels";
import { useOrg } from "@/components/organisation/org-shell";
import { ErrorState, LoadingState, PermissionDenied } from "@/components/states";
import { PageHeader } from "@/components/page";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

// Screen 15 (docs/02 §2.4), hackathon scope: one Zapier endpoint configured on the server (docs/11 §2).
export default function IntegrationsPage() {
  const org = useOrg();
  const queryClient = useQueryClient();
  const integrations = useQuery({
    queryKey: ["org", org.organisation_id, "integrations"],
    queryFn: () => unwrap(api.GET("/api/v1/organisations/{org_id}/integrations", { params: { path: { org_id: org.organisation_id } } })),
  });
  const test = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/integrations/zapier/test", { body: { organisation_id: org.organisation_id } })),
    onSuccess: () => setTimeout(() => queryClient.invalidateQueries({ queryKey: ["org", org.organisation_id, "integrations"] }), 2000),
  });

  if (integrations.error instanceof ApiError && integrations.error.status === 403) {
    return <PermissionDenied message="Only organisation managers can manage integrations." />;
  }
  if (integrations.isPending) return <LoadingState label="Loading integrations…" />;
  if (integrations.error) return <ErrorState onRetry={() => integrations.refetch()} retrying={integrations.isFetching} />;

  return (
    <div className="grid max-w-3xl gap-6">
      <PageHeader
        title="Integrations"
        description="Reclaim sends signed events to your automations. Zapier can't change claims or payments; Reclaim stays the source of truth."
      />
      {integrations.data.map((i) => (
        <section key={i.provider} aria-labelledby={`${i.provider}-heading`} className="grid gap-3 surface p-5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 id={`${i.provider}-heading`} className="flex items-center gap-1.5 font-semibold">
              <Zap className="size-4 text-brand" aria-hidden /> Zapier
            </h2>
            {i.status === "configured" ? (
              <Badge className="bg-success text-success-foreground">
                <CheckCircle2 aria-hidden /> Connected
              </Badge>
            ) : (
              <Badge variant="secondary">
                <CircleSlash aria-hidden /> Not configured
              </Badge>
            )}
            {i.configured_via === "env" && <span className="text-sm text-muted-foreground">Set on the server</span>}
          </div>
          <p className="text-sm text-muted-foreground">{i.note}</p>
          <div className="grid gap-1">
            <h3 className="text-sm font-medium">Events sent</h3>
            <ul className="flex flex-wrap gap-1.5">
              {i.enabled_events.map((e) => (
                <li key={e}>
                  <Badge variant="outline" className="font-mono">
                    {e}
                  </Badge>
                </li>
              ))}
            </ul>
          </div>
          <div className="grid gap-1 text-sm">
            <h3 className="font-medium">Last delivery</h3>
            {i.last_delivery ? (
              <p>
                <span className="font-mono">{i.last_delivery.event_type}</span> · {humanizeKey(i.last_delivery.status)} ·{" "}
                {fullDateTime(i.last_delivery.attempted_at)}
                {i.last_delivery.error && <span className="block text-destructive">Error: {i.last_delivery.error}</span>}
              </p>
            ) : (
              <p className="text-muted-foreground">No deliveries yet.</p>
            )}
          </div>
          <p className="text-xs text-muted-foreground">The signing secret is never shown here. Rotate it in the server settings.</p>
          <div className="grid gap-2">
            <Button className="justify-self-start" variant="outline" onClick={() => test.mutate()} disabled={test.isPending}>
              {test.isPending ? "Sending…" : "Send test event"}
            </Button>
            {test.data && (
              <Alert>
                <AlertDescription>
                  Test event queued ({test.data.status}). {test.data.note}
                </AlertDescription>
              </Alert>
            )}
            {test.error && (
              <p className="text-sm text-destructive" role="alert">
                We couldn&apos;t queue a test event. Try again.
              </p>
            )}
          </div>
        </section>
      ))}
    </div>
  );
}
