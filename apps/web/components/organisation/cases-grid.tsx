"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle } from "lucide-react";
import { AllCommunityModule, ModuleRegistry, themeQuartz, type ColDef, type ICellRendererParams, type ValueFormatterParams } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import type { Schemas } from "@/lib/api/client";
import { categoryLabel, claimStatusLabel, priorityLabel, recoveryStatusLabel, reportStatusLabel } from "@/lib/labels";

ModuleRegistry.registerModules([AllCommunityModule]);

export type CaseRow = Schemas["CaseRow"];

// Community features only (sorting, filters, pagination, quick filter). No Enterprise modules.
// Colours come from the Reclaim tokens in globals.css.
const theme = themeQuartz.withParams({
  accentColor: "var(--brand)",
  foregroundColor: "var(--foreground)",
  backgroundColor: "var(--card)",
  borderColor: "var(--border)",
  headerBackgroundColor: "var(--muted)",
  headerTextColor: "var(--muted-foreground)",
  headerFontWeight: 600,
  rowHoverColor: "var(--accent)",
  selectedRowBackgroundColor: "var(--accent)",
  fontFamily: "inherit",
  fontSize: 14,
  rowHeight: 48,
  headerHeight: 44,
  wrapperBorderRadius: 16,
  borderRadius: 8,
  spacing: 8,
  // Filter popups and pickers: same sizing and surfaces as the app's own dropdowns.
  inputHeight: 40,
  listItemHeight: 36,
  inputBorder: { color: "var(--input)" },
  inputFocusBorder: { color: "var(--brand)" },
  menuBackgroundColor: "var(--popover)",
  menuBorder: { color: "var(--border)" },
  menuShadow: "var(--shadow-overlay)",
  pickerListBackgroundColor: "var(--popover)",
  pickerListBorder: { color: "var(--border)" },
});

/** Priority with text and icon, matching the badges elsewhere (not colour alone). */
function PriorityCell({ value }: ICellRendererParams<CaseRow, CaseRow["priority"]>) {
  if (!value) return null;
  return value === "high" ? (
    <span className="inline-flex items-center gap-1.5 font-semibold">
      <AlertTriangle className="size-3.5 text-warning-foreground" aria-hidden />
      {priorityLabel.high}
    </span>
  ) : (
    <span className="text-muted-foreground">{priorityLabel[value]}</span>
  );
}

const dateFmt = (p: ValueFormatterParams<CaseRow, string>) =>
  p.value ? new Date(p.value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "";
const priorityOrder = { high: 0, medium: 1, low: 2 } as const;

export function CasesGrid({ rows, quickFilter, orgSlug }: { rows: CaseRow[]; quickFilter: string; orgSlug: string }) {
  const router = useRouter();
  // Popups (column filters, pickers) mount on <body> so AG Grid positions them against the page,
  // not the grid wrapper; inside the wrapper they opened on top of their own field.
  // (A grid prop, not markup, so the server/client difference can't cause a hydration mismatch.)
  const popupParent = typeof document === "undefined" ? undefined : document.body;
  const columns = useMemo<ColDef<CaseRow>[]>(
    () => [
      { field: "case_reference", headerName: "Case ID", width: 120, pinned: "left", cellClass: "font-semibold tabular-nums" },
      { field: "item_label", headerName: "Item", minWidth: 140, flex: 1 },
      { field: "category", headerName: "Category", valueFormatter: (p) => (p.value ? categoryLabel[p.value as keyof typeof categoryLabel] : ""), width: 150 },
      { field: "report_status", headerName: "Report", valueFormatter: (p) => (p.value ? reportStatusLabel[p.value as keyof typeof reportStatusLabel] : ""), width: 120 },
      { headerName: "Candidate match", valueGetter: (p) => (p.data?.candidate_match_id ? "Yes" : "No"), width: 180 },
      {
        field: "ai_relevance",
        headerName: "AI relevance",
        filter: "agNumberColumnFilter",
        valueFormatter: (p) => (p.value == null ? "" : String(Math.round(p.value))),
        width: 160,
        headerTooltip: "Candidate relevance, not proof of ownership",
      },
      { field: "location_name", headerName: "Location", width: 240 },
      { field: "reported_at", headerName: "Reported", valueFormatter: dateFmt, filter: "agDateColumnFilter", width: 170 },
      { field: "claim_status", headerName: "Claim", valueFormatter: (p) => (p.value ? claimStatusLabel[p.value as keyof typeof claimStatusLabel] : "None"), width: 140 },
      { field: "recovery_status", headerName: "Recovery", valueFormatter: (p) => (p.value ? recoveryStatusLabel[p.value as keyof typeof recoveryStatusLabel] : "None"), width: 150 },
      {
        field: "priority",
        headerName: "Priority",
        valueFormatter: (p) => (p.value ? priorityLabel[p.value as keyof typeof priorityLabel] : ""),
        comparator: (a: keyof typeof priorityOrder, b: keyof typeof priorityOrder) => priorityOrder[a] - priorityOrder[b],
        cellRenderer: PriorityCell,
        width: 150,
      },
      { field: "updated_at", headerName: "Updated", valueFormatter: dateFmt, sort: "desc", width: 170 },
    ],
    [],
  );

  return (
    <div className="w-full">
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
        domLayout="autoHeight"
        popupParent={popupParent}
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
