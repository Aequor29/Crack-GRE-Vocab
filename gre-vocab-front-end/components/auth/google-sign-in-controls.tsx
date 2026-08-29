"use client";

import { Button } from "@heroui/react/button";
import { Input } from "@heroui/react/input";
import { Link } from "@heroui/react/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { AuthApiError, getGoogleSignInAvailability } from "@/lib/api/auth";
import type { GoogleSignInStatus } from "@/lib/auth-page-query";

type GoogleSignInControlsProps = {
  status?: GoogleSignInStatus;
};

const providerMessages: Partial<Record<GoogleSignInStatus, string>> = {
  cancelled: "Google sign-in was cancelled. No account changes were made.",
  conflict: "This Google identity is already connected to a different account.",
  "provider-error": "Google sign-in could not be completed. Please try again.",
  unavailable: "Google sign-in is not configured for this environment.",
};

export function GoogleSignInControls({ status }: GoogleSignInControlsProps) {
  const auth = useAuth();
  const router = useRouter();
  const googleSignIn = getGoogleSignInAvailability();
  const [linkCancelled, setLinkCancelled] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleConfirmation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setFormError(null);
    setPasswordError(null);
    setSubmitting(true);
    try {
      await auth.confirmGoogleLink({
        password: String(data.get("google_link_password") ?? ""),
      });
      router.replace("/account?google=connected");
      router.refresh();
    } catch (error) {
      if (error instanceof AuthApiError) {
        const fieldError = error.fieldErrors.password?.join(" ") ?? null;
        setPasswordError(fieldError);
        setFormError(fieldError ? null : error.message);
      } else {
        setFormError("Google linking could not be completed. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCancellation() {
    setFormError(null);
    setPasswordError(null);
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
          <Input
            aria-describedby={passwordError ? "google-link-password-error" : undefined}
            aria-invalid={Boolean(passwordError)}
            autoComplete="current-password"
            className="mt-2"
            disabled={submitting}
            fullWidth
            id="google_link_password"
            name="google_link_password"
            required
            type="password"
            variant="secondary"
          />
          {passwordError ? (
            <p
              className="mt-2 text-sm font-medium text-rose-700 dark:text-rose-300"
              id="google-link-password-error"
            >
              {passwordError}
            </p>
          ) : null}
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
          <Button isDisabled={submitting} isPending={submitting} type="submit" variant="primary">
            {submitting ? "Confirming…" : "Confirm Google link"}
          </Button>
          <Button
            isDisabled={submitting}
            onPress={() => void handleCancellation()}
            type="button"
            variant="outline"
          >
            Cancel linking
          </Button>
        </div>
      </form>
    );
  }

  const message = linkCancelled
    ? "Google linking was cancelled. No account changes were made."
    : status
      ? providerMessages[status]
      : googleSignIn.available
        ? null
        : "Google sign-in is unavailable right now. Use email and password instead.";
  const messageRole =
    linkCancelled || status === "cancelled" || (!status && !googleSignIn.available)
      ? "status"
      : "alert";
  const googleActionAvailable = googleSignIn.available && status !== "unavailable";

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
      {googleActionAvailable ? (
        <Link
          className="flex w-full items-center justify-center gap-3 rounded-full border border-foreground/20 px-6 py-3 font-bold transition-colors hover:border-accent hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          href={googleSignIn.url}
        >
          <span aria-hidden="true">G</span>
          Continue with Google
        </Link>
      ) : (
        <Button fullWidth isDisabled type="button" variant="outline">
          <span aria-hidden="true">G</span>
          Continue with Google
        </Button>
      )}
    </div>
  );
}
