import type { Metadata } from "next";

import { PasswordResetRequestForm } from "@/components/auth/password-recovery-form";

export const metadata: Metadata = {
  title: "Reset password",
};

export default function ForgotPasswordPage() {
  return (
    <main
      className="mx-auto grid min-h-[calc(100svh-8rem)] max-w-6xl place-items-center px-5 py-16 sm:px-8"
      id="main-content"
      tabIndex={-1}
    >
      <section
        aria-labelledby="forgot-password-title"
        className="w-full max-w-lg rounded-[2rem] border border-separator bg-surface/90 p-7 shadow-2xl shadow-pale-sky-950/10 sm:p-10 dark:shadow-pale-sky-950/30"
      >
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-accent">Account recovery</p>
        <h1 className="mt-3 text-4xl font-black tracking-[-0.04em]" id="forgot-password-title">
          Reset your password.
        </h1>
        <p className="mb-8 mt-4 leading-7 text-foreground/65">
          Enter your account email. For privacy, the result is the same whether or not an account
          exists.
        </p>
        <PasswordResetRequestForm />
      </section>
    </main>
  );
}
