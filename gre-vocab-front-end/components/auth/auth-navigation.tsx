"use client";

import Link from "next/link";

import { useAuth } from "@/components/auth/auth-provider";

export function AuthNavigation() {
  const { status } = useAuth();
  const authenticated = status === "authenticated";

  return (
    <Link
      className="rounded-full bg-accent px-4 py-2 text-sm font-bold text-accent-foreground shadow-lg shadow-accent/15 transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background motion-reduce:transform-none"
      href={authenticated ? "/account" : "/sign-in"}
    >
      {authenticated ? "Account" : "Sign in"}
    </Link>
  );
}
