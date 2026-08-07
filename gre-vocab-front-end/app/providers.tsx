"use client";

import { ThemeProvider } from "next-themes";
import type { ReactNode } from "react";

import { AuthProvider } from "@/components/auth/auth-provider";

type ProvidersProps = {
  children: ReactNode;
};

export function Providers({ children }: ProvidersProps) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" disableTransitionOnChange enableSystem>
      <AuthProvider>{children}</AuthProvider>
    </ThemeProvider>
  );
}
