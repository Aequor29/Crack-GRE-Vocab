import type { Metadata } from "next";

import { AccountForm } from "@/components/auth/account-form";

export const metadata: Metadata = {
  title: "Sign in",
};

export default function SignInPage() {
  return (
    <main
      className="mx-auto grid min-h-[calc(100svh-8rem)] max-w-6xl place-items-center px-5 py-16 sm:px-8"
      id="main-content"
      tabIndex={-1}
    >
      <section
        aria-labelledby="sign-in-title"
        className="w-full max-w-lg rounded-[2rem] border border-black/10 bg-surface/90 p-7 shadow-2xl shadow-black/10 sm:p-10 dark:border-white/10 dark:shadow-black/30"
      >
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-accent">Learner account</p>
        <h1 className="mt-3 text-4xl font-black tracking-[-0.04em]" id="sign-in-title">
          Welcome back.
        </h1>
        <p className="mb-8 mt-4 leading-7 text-foreground/65">
          Your study plan and progress stay with your server-managed session.
        </p>
        <AccountForm mode="sign-in" />
      </section>
    </main>
  );
}
