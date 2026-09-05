import type { Metadata } from "next";

import { AccountForm } from "@/components/auth/account-form";

export const metadata: Metadata = {
  title: "Create account",
};

export default function SignUpPage() {
  return (
    <main
      className="mx-auto grid min-h-[calc(100svh-8rem)] max-w-6xl place-items-center px-5 py-16 sm:px-8"
      id="main-content"
      tabIndex={-1}
    >
      <section
        aria-labelledby="sign-up-title"
        className="w-full max-w-lg rounded-[2rem] border border-separator bg-surface/90 p-7 shadow-2xl shadow-pale-sky-950/10 sm:p-10 dark:shadow-pale-sky-950/30"
      >
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-accent">Milestone 1</p>
        <h1 className="mt-3 text-4xl font-black tracking-[-0.04em]" id="sign-up-title">
          Create your learner account.
        </h1>
        <p className="mb-8 mt-4 leading-7 text-foreground/65">
          Start clean with an email, a private password, and the name you want to see in the app.
        </p>
        <AccountForm mode="sign-up" />
      </section>
    </main>
  );
}
