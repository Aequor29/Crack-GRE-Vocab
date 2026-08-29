"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { LearningProgressDashboard } from "@/components/progress/learning-progress-dashboard";

export function DashboardShell() {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (auth.status === "unauthenticated") {
      router.replace("/sign-in");
    }
  }, [auth.status, router]);

  if (auth.status === "checking") {
    return (
      <p aria-live="polite" className="text-foreground/70" role="status">
        Loading your dashboard…
      </p>
    );
  }

  if (auth.status === "unavailable") {
    return (
      <section className="rounded-[2rem] border border-black/10 bg-surface p-7 sm:p-10 dark:border-white/10">
        <h1 className="text-4xl font-black tracking-[-0.04em]">Dashboard</h1>
        <p className="mt-4 text-foreground/70" role="alert">
          We couldn&apos;t load your dashboard. Please try again.
        </p>
        <button
          className="mt-6 rounded-full bg-accent px-5 py-2.5 font-bold text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-4 focus-visible:ring-offset-background"
          onClick={() => void auth.refresh()}
          type="button"
        >
          Try again
        </button>
      </section>
    );
  }

  if (auth.status === "unauthenticated" || !auth.account) {
    return (
      <p aria-live="polite" className="text-foreground/70" role="status">
        Redirecting to sign in…
      </p>
    );
  }

  return (
    <section aria-labelledby="dashboard-title" className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-5">
        <h1 className="text-4xl font-black tracking-[-0.04em] sm:text-5xl" id="dashboard-title">
          Dashboard
        </h1>
        <Link
          className="font-bold text-accent underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          href="/account"
        >
          Manage account
        </Link>
      </div>

      <LearningProgressDashboard onAuthenticationExpired={auth.refresh} />
    </section>
  );
}
