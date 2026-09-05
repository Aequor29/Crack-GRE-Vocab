import Link from "next/link";

import { ThemeSwitcher } from "@/components/theme-switcher";

const navigation = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/study", label: "Study" },
] as const;

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-separator bg-background/85 backdrop-blur-xl">
      <div className="mx-auto flex min-h-16 max-w-6xl items-center justify-between gap-4 px-5 sm:px-8">
        <Link
          aria-label="Crack GRE Vocab home"
          className="group inline-flex items-center gap-3 rounded-xl font-semibold tracking-tight outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-4 focus-visible:ring-offset-background"
          href="/dashboard"
        >
          <span
            aria-hidden="true"
            className="grid size-9 place-items-center rounded-xl bg-accent text-sm font-black text-accent-foreground shadow-lg shadow-accent/20 transition-transform group-hover:-rotate-3"
          >
            C
          </span>
          <span className="hidden sm:inline">Crack GRE Vocab</span>
          <span className="sm:hidden">Crack GRE</span>
        </Link>

        <div className="flex items-center gap-1 sm:gap-2">
          <nav aria-label="Primary" className="flex items-center gap-1">
            {navigation.map((item) => (
              <Link
                className="inline-flex rounded-full px-3 py-2 text-sm font-medium text-foreground/70 transition-colors hover:bg-surface hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                href={item.href}
                key={item.href}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <ThemeSwitcher />
        </div>
      </div>
    </header>
  );
}
