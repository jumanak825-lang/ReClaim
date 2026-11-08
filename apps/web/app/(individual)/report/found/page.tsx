"use client";

import { useSearchParams } from "next/navigation";
import { FoundWizard } from "@/components/reports/found-wizard";
import { ResumeReport, wizardParams } from "@/components/reports/resume-report";

export default function ReportFoundPage() {
  const searchParams = useSearchParams();
  const { id, step } = wizardParams(searchParams);
  // ?org=<slug> comes from the organisation portal's "Log found item".
  if (!id) return <FoundWizard preselectOrgSlug={searchParams.get("org")} />;
  return <ResumeReport id={id} type="found">{(r) => <FoundWizard key={r.id} existing={r} initialStep={step} />}</ResumeReport>;
}
