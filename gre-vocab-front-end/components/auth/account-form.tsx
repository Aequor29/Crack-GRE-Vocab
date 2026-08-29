"use client";

import { Button } from "@heroui/react/button";
import { Input } from "@heroui/react/input";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { GoogleSignInControls } from "@/components/auth/google-sign-in-controls";
import { AuthApiError, type AuthFieldErrors } from "@/lib/api/auth";
import type { GoogleSignInStatus } from "@/lib/auth-page-query";

type AccountFormProps = {
  googleStatus?: GoogleSignInStatus;
  mode: "sign-in" | "sign-up";
};

function FieldError({ id, messages }: { id: string; messages?: string[] }) {
  return messages?.length ? (
    <p className="mt-2 text-sm font-medium text-rose-700 dark:text-rose-300" id={id}>
      {messages.join(" ")}
    </p>
  ) : null;
}

export function AccountForm({ googleStatus, mode }: AccountFormProps) {
  const router = useRouter();
  const auth = useAuth();
  const [fieldErrors, setFieldErrors] = useState<AuthFieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const signingUp = mode === "sign-up";

  if (auth.status === "checking") {
    return (
      <p aria-live="polite" className="text-sm text-foreground/70" role="status">
        Checking your account…
      </p>
    );
  }

  if (auth.status === "authenticated") {
    return (
      <div className="space-y-4">
        <p className="text-foreground/70">You are already signed in.</p>
        <Link
          className="font-bold text-accent underline-offset-4 hover:underline"
          href="/dashboard"
        >
          Go to your dashboard
        </Link>
      </div>
    );
  }

  if (googleStatus === "link-required") {
    return <GoogleSignInControls status={googleStatus} />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setFieldErrors({});
    setFormError(null);
    setSubmitting(true);

    try {
      const email = String(data.get("email") ?? "");
      const password = String(data.get("password") ?? "");
      if (signingUp) {
        await auth.signUp({
          display_name: String(data.get("display_name") ?? ""),
          email,
          password,
        });
      } else {
        await auth.signIn({ email, password });
      }
      router.replace("/dashboard");
      router.refresh();
    } catch (error) {
      if (error instanceof AuthApiError) {
        setFieldErrors(error.fieldErrors);
        setFormError(error.message);
      } else {
        setFormError("Something unexpected happened. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  const emailErrorId = fieldErrors.email?.length ? `${mode}-email-error` : undefined;
  const nameErrorId = fieldErrors.display_name?.length ? `${mode}-name-error` : undefined;
  const passwordErrorId = fieldErrors.password?.length ? `${mode}-password-error` : undefined;

  return (
    <form className="space-y-5" noValidate onSubmit={handleSubmit}>
      <GoogleSignInControls status={googleStatus} />

      <div aria-hidden="true" className="flex items-center gap-4">
        <span className="h-px flex-1 bg-foreground/15" />
        <span className="text-xs font-bold uppercase tracking-[0.16em] text-foreground/50">or</span>
        <span className="h-px flex-1 bg-foreground/15" />
      </div>

      {auth.status === "unavailable" ? (
        <p className="rounded-2xl bg-amber-500/10 p-4 text-sm text-foreground" role="status">
          We couldn&apos;t connect. You can still try submitting the form again.
        </p>
      ) : null}

      {signingUp ? (
        <div>
          <label className="text-sm font-bold" htmlFor="display_name">
            Display name
          </label>
          <Input
            aria-describedby={nameErrorId}
            aria-invalid={Boolean(nameErrorId)}
            autoComplete="name"
            className="mt-2"
            disabled={submitting}
            fullWidth
            id="display_name"
            maxLength={80}
            name="display_name"
            required
            variant="secondary"
          />
          <FieldError id={`${mode}-name-error`} messages={fieldErrors.display_name} />
        </div>
      ) : null}

      <div>
        <label className="text-sm font-bold" htmlFor="email">
          Email
        </label>
        <Input
          aria-describedby={emailErrorId}
          aria-invalid={Boolean(emailErrorId)}
          autoComplete="email"
          className="mt-2"
          disabled={submitting}
          fullWidth
          id="email"
          inputMode="email"
          maxLength={254}
          name="email"
          required
          type="email"
          variant="secondary"
        />
        <FieldError id={`${mode}-email-error`} messages={fieldErrors.email} />
      </div>

      <div>
        <label className="text-sm font-bold" htmlFor="password">
          Password
        </label>
        <Input
          aria-describedby={passwordErrorId}
          aria-invalid={Boolean(passwordErrorId)}
          autoComplete={signingUp ? "new-password" : "current-password"}
          className="mt-2"
          disabled={submitting}
          fullWidth
          id="password"
          minLength={8}
          name="password"
          required
          type="password"
          variant="secondary"
        />
        <FieldError id={`${mode}-password-error`} messages={fieldErrors.password} />
        {!signingUp ? (
          <p className="mt-3 text-right text-sm">
            <Link
              className="font-bold text-accent underline-offset-4 hover:underline"
              href="/forgot-password"
            >
              Forgot password?
            </Link>
          </p>
        ) : null}
      </div>

      {formError ? (
        <p
          className="rounded-2xl bg-rose-500/10 p-4 text-sm font-medium text-foreground"
          role="alert"
        >
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
        {submitting ? "Working…" : signingUp ? "Create account" : "Sign in"}
      </Button>

      <p className="text-center text-sm text-foreground/65">
        {signingUp ? "Already have an account?" : "New to Crack GRE Vocab?"}{" "}
        <Link
          className="font-bold text-accent underline-offset-4 hover:underline"
          href={signingUp ? "/sign-in" : "/sign-up"}
        >
          {signingUp ? "Sign in" : "Create one"}
        </Link>
      </p>
    </form>
  );
}
