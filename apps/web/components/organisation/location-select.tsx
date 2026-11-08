"use client";

import { MapPin } from "lucide-react";
import type { Schemas } from "@/lib/api/client";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const ALL_LOCATIONS = "all";

export function LocationSelect({
  locations,
  value,
  onChange,
  allLabel,
}: {
  locations: Schemas["LocationOut"][];
  value: string;
  onChange: (value: string) => void;
  allLabel: string;
}) {
  if (locations.length === 1) {
    return (
      <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <MapPin className="size-4" aria-hidden /> {locations[0].name}
      </p>
    );
  }
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-64" aria-label="Location">
        <MapPin aria-hidden />
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL_LOCATIONS}>{allLabel}</SelectItem>
        {locations.map((l) => (
          <SelectItem key={l.id} value={l.id}>
            {l.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
