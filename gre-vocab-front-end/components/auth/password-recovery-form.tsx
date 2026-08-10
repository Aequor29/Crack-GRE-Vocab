"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";

import { AuthApiError, confirmPasswordReset, requestPasswordReset } from "@/lib/api/auth";

const inputClassName =
  "mt-2 w-full rounded-2xl border border-black/15 bg-background px-4 py-3 text-base text-foreground outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/25 disabled:cursor-wait disabled:opacity-60 dark:border-white/15";

export function PasswordResetRequestForm() {
  const [emailError, setEmailError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setEmailError(null);
    setFormError(null);
    setSubmitting(true);

    try {
      const message = await requestPasswordReset({
        email: String(data.get("email") ?? ""),
      });
      setResult(message);
    } catch (error) {
      if (error instanceof AuthApiError) {
        setEmailError(error.fieldErrors.email?.join(" ") ?? null);
        setFormError(error.message);
      } else {
        setFormError("Something unexpected happened. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (result) {
    return (
      <div className="space-y-5">
        <p className="rounded-2xl bg-accent/10 p-4 text-sm font-medium" role="status">
          {result}
        </p>
        <Link className="font-bold text-accent underline-offset-4 hover:underline" href="/sign-in">
          Return to sign in
        </Link>
      </div>
    );
  }

  const emailErrorId = emailError ? "password-reset-email-error" : undefined;

  return (
    <form className="space-y-5" noValidate onSubmit={handleSubmit}>
      <div>
        <label className="text-sm font-bold" htmlFor="password-reset-email">
          Email
        </label>
        <input
          aria-describedby={emailErrorId}
          aria-invalid={Boolean(emailErrorId)}
          autoComplete="email"
          className={inputClassName}
          disabled={submitting}
          id="password-reset-email"
          inputMode="email"
          maxLength={254}
          name="email"
          required
          type="email"
        />
        {emailError ? (
          <p
            className="mt-2 text-sm font-medium text-rose-700 dark:text-rose-300"
            id="password-reset-email-error"
          >
            {emailError}
          </p>
        ) : null}
      </div>

      {formError ? (
        <p className="rounded-2xl bg-rose-500/10 p-4 text-sm font-medium" role="alert">
          {formError}
        </p>
      ) : null}

      <button
        className="w-full rounded-full bg-accent px-6 py-3 font-bold text-accent-foreground shadow-xl shadow-accent/20 transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-4 focus-visible:ring-offset-background disabled:cursor-wait disabled:opacity-60 motion-reduce:transform-none"
        disabled={submitting}
        type="submit"
      >
        {submitting ? "Sending…" : "Send reset link"}
      </button>
    </form>
  );
}

export function PasswordResetConfirmationForm({
  token,
  uid,
}: {
  token: string | null;
  uid: string | null;
}) {
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!token || !uid) {
    return (
      <div className="space-y-5">
        <p className="rounded-2xl bg-rose-500/10 p-4 text-sm font-medium" role="alert">
          This password reset link is invalid or has expired.
        </p>
        <Link
          className="font-bold text-accent underline-offset-4 hover:underline"
          href="/forgot-password"
        >
          Request a new reset link
        </Link>
      </div>
    );
  }

  const confirmedToken = token;
  const confirmedUid = uid;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setPasswordError(null);
    setFormError(null);
    setSubmitting(true);

    try {
      const message = await confirmPasswordReset({
        password: String(data.get("password") ?? ""),
        token: confirmedToken,
        uid: confirmedUid,
      });
      setResult(message);
    } catch (error) {
      if (error instanceof AuthApiError) {
        setPasswordError(error.fieldErrors.password?.join(" ") ?? null);
        setFormError(error.message);
      } else {
        setFormError("Something unexpected happened. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (result) {
    return (
      <div className="space-y-5">
        <p className="rounded-2xl bg-accent/10 p-4 text-sm font-medium" role="status">
          {result}
        </p>
        <Link className="font-bold text-accent underline-offset-4 hover:underline" href="/sign-in">
          Sign in
        </Link>
      </div>
    );
  }

  const passwordErrorId = passwordError ? "password-reset-password-error" : undefined;

  return (
    <form className="space-y-5" noValidate onSubmit={handleSubmit}>
      <div>
        <label className="text-sm font-bold" htmlFor="password-reset-password">
          New password
        </label>
        <input
          aria-describedby={passwordErrorId}
          aria-invalid={Boolean(passwordErrorId)}
          autoComplete="new-password"
          className={inputClassName}
          disabled={submitting}
          id="password-reset-password"
          minLength={8}
          name="password"
          required
          type="password"
        />
        {passwordError ? (
          <p
            className="mt-2 text-sm font-medium text-rose-700 dark:text-rose-300"
            id="password-reset-password-error"
          >
            {passwordError}
          </p>
        ) : null}
      </div>

      {formError ? (
        <p className="rounded-2xl bg-rose-500/10 p-4 text-sm font-medium" role="alert">
          {formError}
        </p>
      ) : null}

      <button
        className="w-full rounded-full bg-accent px-6 py-3 font-bold text-accent-foreground shadow-xl shadow-accent/20 transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-4 focus-visible:ring-offset-background disabled:cursor-wait disabled:opacity-60 motion-reduce:transform-none"
        disabled={submitting}
        type="submit"
      >
        {submitting ? "Resetting…" : "Reset password"}
      </button>
    </form>
  );
}
