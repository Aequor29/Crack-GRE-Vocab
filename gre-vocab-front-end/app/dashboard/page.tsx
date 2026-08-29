import type { Metadata } from "next";

import { DashboardShell } from "@/components/dashboard/dashboard-shell";

export const metadata: Metadata = {
  title: "Dashboard",
};

export default function DashboardPage() {
  return (
    <main
      className="mx-auto min-h-[calc(100svh-8rem)] max-w-6xl px-5 py-10 sm:px-8 lg:py-16"
      id="main-content"
      tabIndex={-1}
    >
      <DashboardShell />
    </main>
  );
}
