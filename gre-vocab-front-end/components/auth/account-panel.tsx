"use client";

import { Button } from "@heroui/react/button";
import { Card } from "@heroui/react/card";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { AuthApiError } from "@/lib/api/auth";

export function AccountPanel({ googleConnected = false }: { googleConnected?: boolean }) {
  const auth = useAuth();
  const router = useRouter();
  const [signOutError, setSignOutError] = useState<string | null>(null);
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    if (auth.status === "unauthenticated") {
      router.replace("/sign-in");
    }
  }, [auth.status, router]);

  if (auth.status === "checking") {
    return (
      <p aria-live="polite" className="text-foreground/70" role="status">
        Loading your account…
      </p>
    );
  }

  if (auth.status === "unavailable") {
    return (
      <div className="space-y-5">
        <p className="text-foreground/70" role="alert">
          We couldn&apos;t load your account. Please try again.
        </p>
        <Button onPress={() => void auth.refresh()} type="button" variant="outline">
          Try again
        </Button>
      </div>
    );
  }

  if (auth.status === "unauthenticated" || !auth.account) {
    return (
      <div className="space-y-4">
        <p className="text-foreground/70" role="status">
          Sign in is required to view this page.
        </p>
        <Link className="font-bold text-accent underline-offset-4 hover:underline" href="/sign-in">
          Continue to sign in
        </Link>
      </div>
    );
  }

  async function handleSignOut() {
    setSignOutError(null);
    setSigningOut(true);
    try {
      await auth.signOut();
      router.replace("/sign-in");
      router.refresh();
    } catch (error) {
      setSignOutError(
        error instanceof AuthApiError
          ? error.message
          : "Something unexpected happened. Please try again.",
      );
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <div className="space-y-8">
      {googleConnected ? (
        <p className="rounded-2xl bg-accent/10 p-4 text-sm font-medium" role="status">
          Google sign-in is connected to this account.
        </p>
      ) : null}
      <Card className="overflow-hidden" variant="secondary">
        <dl className="divide-y divide-black/10 dark:divide-white/10">
          <div className="grid gap-1 p-5 sm:grid-cols-[8rem_1fr] sm:gap-4">
            <dt className="text-sm font-bold text-foreground/60">Display name</dt>
            <dd className="font-semibold">{auth.account.display_name}</dd>
          </div>
          <div className="grid gap-1 p-5 sm:grid-cols-[8rem_1fr] sm:gap-4">
            <dt className="text-sm font-bold text-foreground/60">Email</dt>
            <dd className="break-all">{auth.account.email}</dd>
          </div>
        </dl>
      </Card>

      {signOutError ? (
        <p className="rounded-2xl bg-rose-500/10 p-4 text-sm font-medium" role="alert">
          {signOutError}
        </p>
      ) : null}

      <Button
        isDisabled={signingOut}
        isPending={signingOut}
        onPress={() => void handleSignOut()}
        type="button"
        variant="danger-soft"
      >
        {signingOut ? "Signing out…" : "Sign out"}
      </Button>
    </div>
  );
}
