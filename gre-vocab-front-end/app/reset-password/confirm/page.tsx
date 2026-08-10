import type { Metadata } from "next";

import { PasswordResetConfirmationForm } from "@/components/auth/password-recovery-form";

export const metadata: Metadata = {
  title: "Choose a new password",
};

type PasswordResetConfirmationPageProps = {
  searchParams: Promise<{
    token?: string | string[];
    uid?: string | string[];
  }>;
};

function firstSearchParameter(value: string | string[] | undefined): string | null {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }
  return value ?? null;
}

export default async function PasswordResetConfirmationPage({
  searchParams,
}: PasswordResetConfirmationPageProps) {
  const parameters = await searchParams;

  return (
    <main
      className="mx-auto grid min-h-[calc(100svh-8rem)] max-w-6xl place-items-center px-5 py-16 sm:px-8"
      id="main-content"
      tabIndex={-1}
    >
      <section
        aria-labelledby="password-reset-confirmation-title"
        className="w-full max-w-lg rounded-[2rem] border border-black/10 bg-surface/90 p-7 shadow-2xl shadow-black/10 sm:p-10 dark:border-white/10 dark:shadow-black/30"
      >
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-accent">Account recovery</p>
        <h1
          className="mt-3 text-4xl font-black tracking-[-0.04em]"
          id="password-reset-confirmation-title"
        >
          Choose a new password.
        </h1>
        <p className="mb-8 mt-4 leading-7 text-foreground/65">
          Completing this reset signs out every existing session for your account.
        </p>
        <PasswordResetConfirmationForm
          token={firstSearchParameter(parameters.token)}
          uid={firstSearchParameter(parameters.uid)}
        />
      </section>
    </main>
  );
}
