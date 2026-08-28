"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/auth/auth-provider";

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
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-foreground/55">
            Dashboard
          </p>
          <h1
            className="mt-3 text-4xl font-black tracking-[-0.04em] sm:text-5xl"
            id="dashboard-title"
          >
            Welcome back, <span className="text-accent">{auth.account.display_name}</span>
          </h1>
        </div>
        <Link
          className="font-bold text-accent underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          href="/account"
        >
          Manage account
        </Link>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <article className="rounded-[2rem] border border-black/10 bg-surface p-7 sm:p-8 dark:border-white/10">
          <h2 className="text-2xl font-black tracking-tight">Study</h2>
          <p className="mt-3 leading-7 text-foreground/65">
            Continue an active session or start your next set of words.
          </p>
          <Link
            className="mt-7 inline-flex rounded-full bg-accent px-6 py-3 font-bold text-accent-foreground shadow-lg shadow-accent/15 transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-4 focus-visible:ring-offset-background motion-reduce:transform-none"
            href="/study"
          >
            Start studying
          </Link>
        </article>

        <article className="rounded-[2rem] border border-black/10 bg-surface p-7 sm:p-8 dark:border-white/10">
          <h2 className="text-2xl font-black tracking-tight">Progress</h2>
          <p className="mt-3 leading-7 text-foreground/65">
            Your study history and progress summaries will appear here.
          </p>
        </article>
      </div>
    </section>
  );
}
