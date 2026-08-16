"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { AuthApiError, googleSignInUrl } from "@/lib/api/auth";

export type GoogleSignInStatus =
  | "cancelled"
  | "conflict"
  | "link-required"
  | "provider-error"
  | "unavailable";

type GoogleSignInControlsProps = {
  status?: GoogleSignInStatus;
};

const providerMessages: Partial<Record<GoogleSignInStatus, string>> = {
  cancelled: "Google sign-in was cancelled. No account changes were made.",
  conflict: "This Google identity is already connected to a different account.",
  "provider-error": "Google sign-in could not be completed. Please try again.",
  unavailable: "Google sign-in is not configured for this environment.",
};

const inputClassName =
  "mt-2 w-full rounded-2xl border border-black/15 bg-background px-4 py-3 text-base text-foreground outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/25 disabled:cursor-wait disabled:opacity-60 dark:border-white/15";

export function GoogleSignInControls({ status }: GoogleSignInControlsProps) {
  const auth = useAuth();
  const router = useRouter();
  const [linkCancelled, setLinkCancelled] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleConfirmation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setFormError(null);
    setSubmitting(true);
    try {
      await auth.confirmGoogleLink({
        password: String(data.get("google_link_password") ?? ""),
      });
      router.replace("/account?google=connected");
      router.refresh();
    } catch (error) {
      setFormError(
        error instanceof AuthApiError
          ? error.message
          : "Google linking could not be completed. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCancellation() {
    setFormError(null);
    setSubmitting(true);
    try {
      await auth.cancelGoogleLink();
      setLinkCancelled(true);
    } catch (error) {
      setFormError(
        error instanceof AuthApiError
          ? error.message
          : "Google linking could not be cancelled. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (status === "link-required" && !linkCancelled) {
    return (
      <form className="space-y-5" noValidate onSubmit={handleConfirmation}>
        <p className="rounded-2xl bg-accent/10 p-4 text-sm text-foreground" role="status">
          Confirm this is your existing account before linking Google.
        </p>
        <div>
          <label className="text-sm font-bold" htmlFor="google_link_password">
            Current password
          </label>
          <input
            aria-describedby={formError ? "google-link-error" : undefined}
            aria-invalid={Boolean(formError)}
            autoComplete="current-password"
            className={inputClassName}
            disabled={submitting}
            id="google_link_password"
            name="google_link_password"
            required
            type="password"
          />
        </div>
        {formError ? (
          <p
            className="rounded-2xl bg-rose-500/10 p-4 text-sm font-medium"
            id="google-link-error"
            role="alert"
          >
            {formError}
          </p>
        ) : null}
        <div className="grid gap-3 sm:grid-cols-2">
          <button
            className="rounded-full bg-accent px-5 py-3 font-bold text-accent-foreground disabled:cursor-wait disabled:opacity-60"
            disabled={submitting}
            type="submit"
          >
            {submitting ? "Confirming…" : "Confirm Google link"}
          </button>
          <button
            className="rounded-full border border-foreground/20 px-5 py-3 font-bold disabled:cursor-wait disabled:opacity-60"
            disabled={submitting}
            onClick={() => void handleCancellation()}
            type="button"
          >
            Cancel linking
          </button>
        </div>
      </form>
    );
  }

  const message = linkCancelled
    ? "Google linking was cancelled. No account changes were made."
    : status
      ? providerMessages[status]
      : null;
  const messageRole = linkCancelled || status === "cancelled" ? "status" : "alert";

  return (
    <div className="space-y-4">
      {message ? (
        <p
          className={`rounded-2xl p-4 text-sm font-medium ${
            messageRole === "alert" ? "bg-rose-500/10" : "bg-accent/10"
          }`}
          role={messageRole}
        >
          {message}
        </p>
      ) : null}
      <a
        className="flex w-full items-center justify-center gap-3 rounded-full border border-foreground/20 px-6 py-3 font-bold transition-colors hover:border-accent hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        href={googleSignInUrl()}
      >
        <span aria-hidden="true">G</span>
        Continue with Google
      </a>
    </div>
  );
}
