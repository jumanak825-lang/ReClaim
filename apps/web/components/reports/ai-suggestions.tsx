"use client";

import { useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { categoryLabel } from "@/lib/labels";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

type Extraction = Schemas["ExtractionOut"];
export type SuggestionField = "category" | "item_label" | "brand" | "model" | "colour";

const fieldLabel: Record<SuggestionField, string> = {
  category: "Category",
  item_label: "Item",
  brand: "Brand",
  model: "Model",
  colour: "Colour",
};

/**
 * Starts extraction for the report, polls until it finishes, and offers each suggestion that
 * differs from what the user entered. Nothing is applied without the user choosing it (FR-005).
 */
export function AiSuggestions({
  reportId,
  current,
  onUse,
}: {
  reportId: string;
  current: Record<SuggestionField, string>;
  onUse: (field: SuggestionField, value: string) => void;
}) {
  const start = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/reports/{report_id}/extract", { params: { path: { report_id: reportId } } })),
  });
  const { mutate } = start;
  useEffect(() => mutate(), [mutate, reportId]);

  const extraction = useQuery({
    queryKey: ["reports", reportId, "extraction"],
    queryFn: () => unwrap(api.GET("/api/v1/reports/{report_id}/extraction", { params: { path: { report_id: reportId } } })),
    enabled: start.isSuccess,
    refetchInterval: (q) => (q.state.data?.status === "processing" ? 1000 : false),
    staleTime: 0,
  });

  const data = extraction.data;
  if (start.isError || extraction.isError || data?.status === "failed") {
    return (
      <Alert>
        <AlertTitle>Suggestions aren&apos;t available right now</AlertTitle>
        <AlertDescription>Check your details below and continue. Matching still works without them.</AlertDescription>
      </Alert>
    );
  }
  if (!data || data.status !== "completed") {
    return (
      <p className="flex items-center gap-2 text-muted-foreground" role="status">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Reading your description for suggestions…
      </p>
    );
  }

  const suggestions = suggestionsFrom(data).filter((s) => s.value.toLowerCase() !== current[s.field].trim().toLowerCase());

  return (
    <section aria-labelledby="ai-heading" className="grid gap-3 surface-ai p-4">
      <h3 id="ai-heading" className="flex items-center gap-2 font-medium">
        <Sparkles className="size-4 text-brand" aria-hidden />
        {data.is_fallback ? "Suggestions (basic keyword matching, AI unavailable)" : "AI suggestions"}
      </h3>
      <p className="text-sm text-muted-foreground">{data.disclaimer}</p>
      {suggestions.length ? (
        <ul className="grid gap-2">
          {suggestions.map((s) => (
            <li key={s.field} className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-card p-3">
              <span>
                <span className="text-muted-foreground">{fieldLabel[s.field]}:</span> <strong>{s.display}</strong>{" "}
                <span className="text-sm text-muted-foreground">({Math.round(s.confidence * 100)}% confidence)</span>
              </span>
              <Button type="button" size="sm" variant="outline" onClick={() => onUse(s.field, s.value)}>
                Use this
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm">Your details already match the suggestions.</p>
      )}
    </section>
  );
}

function suggestionsFrom(e: Extraction) {
  const out: { field: SuggestionField; value: string; display: string; confidence: number }[] = [];
  for (const field of Object.keys(fieldLabel) as SuggestionField[]) {
    const f = e[field];
    if (!f.value) continue;
    const display = field === "category" ? (categoryLabel[f.value as keyof typeof categoryLabel] ?? f.value) : f.value;
    out.push({ field, value: f.value, display, confidence: f.confidence });
  }
  return out;
}
