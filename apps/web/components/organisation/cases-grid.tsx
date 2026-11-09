"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { AllCommunityModule, ModuleRegistry, themeQuartz, type ColDef, type ValueFormatterParams } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import type { Schemas } from "@/lib/api/client";
import { categoryLabel, claimStatusLabel, priorityLabel, recoveryStatusLabel, reportStatusLabel } from "@/lib/labels";

ModuleRegistry.registerModules([AllCommunityModule]);

export type CaseRow = Schemas["CaseRow"];

// Community features only (sorting, filters, pagination, quick filter). No Enterprise modules.
const theme = themeQuartz.withParams({
  accentColor: "var(--primary)",
  foregroundColor: "var(--foreground)",
  backgroundColor: "var(--card)",
  borderColor: "var(--border)",
  headerBackgroundColor: "var(--muted)",
  fontFamily: "inherit",
});

const dateFmt = (p: ValueFormatterParams<CaseRow, string>) =>
  p.value ? new Date(p.value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "";
const priorityOrder = { high: 0, medium: 1, low: 2 } as const;

export function CasesGrid({ rows, quickFilter, orgSlug }: { rows: CaseRow[]; quickFilter: string; orgSlug: string }) {
  const router = useRouter();
  const columns = useMemo<ColDef<CaseRow>[]>(
    () => [
      { field: "case_reference", headerName: "Case ID", width: 120, pinned: "left" },
      { field: "item_label", headerName: "Item", minWidth: 140, flex: 1 },
      { field: "category", headerName: "Category", valueFormatter: (p) => (p.value ? categoryLabel[p.value as keyof typeof categoryLabel] : ""), width: 150 },
      { field: "report_status", headerName: "Report", valueFormatter: (p) => (p.value ? reportStatusLabel[p.value as keyof typeof reportStatusLabel] : ""), width: 120 },
      { headerName: "Candidate match", valueGetter: (p) => (p.data?.candidate_match_id ? "Yes" : "No"), width: 150 },
      {
        field: "ai_relevance",
        headerName: "AI relevance",
        filter: "agNumberColumnFilter",
        valueFormatter: (p) => (p.value == null ? "" : String(Math.round(p.value))),
        width: 130,
        headerTooltip: "Candidate relevance, not proof of ownership",
      },
      { field: "location_name", headerName: "Location", width: 190 },
      { field: "reported_at", headerName: "Reported", valueFormatter: dateFmt, filter: "agDateColumnFilter", width: 170 },
      { field: "claim_status", headerName: "Claim", valueFormatter: (p) => (p.value ? claimStatusLabel[p.value as keyof typeof claimStatusLabel] : "None"), width: 140 },
      { field: "recovery_status", headerName: "Recovery", valueFormatter: (p) => (p.value ? recoveryStatusLabel[p.value as keyof typeof recoveryStatusLabel] : "None"), width: 150 },
      {
        field: "priority",
        headerName: "Priority",
        valueFormatter: (p) => (p.value ? priorityLabel[p.value as keyof typeof priorityLabel] : ""),
        comparator: (a: keyof typeof priorityOrder, b: keyof typeof priorityOrder) => priorityOrder[a] - priorityOrder[b],
        width: 150,
      },
      { field: "updated_at", headerName: "Updated", valueFormatter: dateFmt, sort: "desc", width: 170 },
    ],
    [],
  );

  return (
    <div style={{ height: 560 }} className="w-full">
      <AgGridReact<CaseRow>
        theme={theme}
        rowData={rows}
        columnDefs={columns}
        defaultColDef={{ sortable: true, filter: true, resizable: true }}
        getRowId={(p) => p.data.id}
        quickFilterText={quickFilter}
        pagination
        paginationPageSize={20}
        paginationPageSizeSelector={[20, 50, 100]}
        rowSelection={undefined}
        onRowClicked={(e) => e.data && router.push(`/org/${orgSlug}/cases/${e.data.id}`)}
        // Keyboard users: Enter on a focused cell opens the case too.
        onCellKeyDown={(e) => {
          if ((e.event as KeyboardEvent | null)?.key === "Enter" && e.data) router.push(`/org/${orgSlug}/cases/${e.data.id}`);
        }}
        rowClass="cursor-pointer"
        overlayNoRowsTemplate="No cases match these filters."
      />
    </div>
  );
}
