import type { Metadata } from "next";

import { AccountPanel } from "@/components/auth/account-panel";

export const metadata: Metadata = {
  title: "Your account",
};

type AccountPageProps = {
  searchParams: Promise<{ google?: string | string[] }>;
};

export default async function AccountPage({ searchParams }: AccountPageProps) {
  const googleConnected = (await searchParams).google === "connected";
  return (
    <main
      className="mx-auto min-h-[calc(100svh-8rem)] max-w-4xl px-5 py-16 sm:px-8 lg:py-24"
      id="main-content"
      tabIndex={-1}
    >
      <section
        aria-labelledby="account-title"
        className="rounded-[2rem] border border-black/10 bg-surface/90 p-7 shadow-2xl shadow-black/10 sm:p-10 dark:border-white/10 dark:shadow-black/30"
      >
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-accent">Account</p>
        <h1 className="mt-3 text-4xl font-black tracking-[-0.04em] sm:text-5xl" id="account-title">
          Your profile
        </h1>
        <p className="mb-10 mt-4 max-w-2xl leading-7 text-foreground/65">
          Review your account details or sign out when you&apos;re finished.
        </p>
        <AccountPanel googleConnected={googleConnected} />
      </section>
    </main>
  );
}
