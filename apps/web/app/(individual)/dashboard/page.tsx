"use client";

import { useMe } from "@/lib/api/me";

// Shell only. Summary cards and recent activity (docs/02 Screen 3) come in the next phase.
export default function DashboardPage() {
  const { data: me } = useMe();
  return (
    <h1 className="text-2xl font-semibold tracking-tight">Welcome, {me?.display_name}</h1>
  );
}
