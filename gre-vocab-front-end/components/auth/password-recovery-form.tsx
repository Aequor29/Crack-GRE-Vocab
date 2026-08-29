"use client";

import { Button } from "@heroui/react/button";
import { Input } from "@heroui/react/input";
import Link from "next/link";
import { type FormEvent, useState } from "react";

import { AuthApiError, confirmPasswordReset, requestPasswordReset } from "@/lib/api/auth";

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
        <Input
          aria-describedby={emailErrorId}
          aria-invalid={Boolean(emailErrorId)}
          autoComplete="email"
          className="mt-2"
          disabled={submitting}
          fullWidth
          id="password-reset-email"
          inputMode="email"
          maxLength={254}
          name="email"
          required
          type="email"
          variant="secondary"
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

      <Button
        fullWidth
        isDisabled={submitting}
        isPending={submitting}
        type="submit"
        variant="primary"
      >
        {submitting ? "Sending…" : "Send reset link"}
      </Button>
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
        <Input
          aria-describedby={passwordErrorId}
          aria-invalid={Boolean(passwordErrorId)}
          autoComplete="new-password"
          className="mt-2"
          disabled={submitting}
          fullWidth
          id="password-reset-password"
          minLength={8}
          name="password"
          required
          type="password"
          variant="secondary"
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

      <Button
        fullWidth
        isDisabled={submitting}
        isPending={submitting}
        type="submit"
        variant="primary"
      >
        {submitting ? "Resetting…" : "Reset password"}
      </Button>
    </form>
  );
}
