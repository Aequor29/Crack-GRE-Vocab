import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { Providers } from "@/app/providers";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Crack GRE Vocab",
    template: "%s · Crack GRE Vocab",
  },
  description: "A focused GRE vocabulary experience for building durable recall.",
};

export const viewport: Viewport = {
  colorScheme: "light dark",
  themeColor: [
    { color: "#eef4f6", media: "(prefers-color-scheme: light)" },
    { color: "#0c1418", media: "(prefers-color-scheme: dark)" },
  ],
};

type RootLayoutProps = {
  children: ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html data-scroll-behavior="smooth" lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background text-foreground antialiased">
        <Providers>
          <a
            className="fixed left-4 top-4 z-50 -translate-y-24 rounded-lg bg-accent px-4 py-2 font-semibold text-accent-foreground transition-transform focus:translate-y-0"
            href="#main-content"
          >
            Skip to content
          </a>
          <div className="flex min-h-screen flex-col">
            <SiteHeader />
            <div className="flex-1">{children}</div>
            <SiteFooter />
          </div>
        </Providers>
      </body>
    </html>
  );
}
