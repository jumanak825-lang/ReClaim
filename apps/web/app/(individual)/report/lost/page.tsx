"use client";

import { useSearchParams } from "next/navigation";
import { LostWizard } from "@/components/reports/lost-wizard";
import { ResumeReport, wizardParams } from "@/components/reports/resume-report";

export default function ReportLostPage() {
  const { id, step } = wizardParams(useSearchParams());
  if (!id) return <LostWizard />;
  // key: start fresh if the id in the URL changes.
  return <ResumeReport id={id} type="lost">{(r) => <LostWizard key={r.id} existing={r} initialStep={step} />}</ResumeReport>;
}
