"use client";

import { Button } from "@heroui/react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

const themes = ["system", "light", "dark"] as const;

type ThemeName = (typeof themes)[number];

function isThemeName(value: string | undefined): value is ThemeName {
  return themes.some((theme) => theme === value);
}

function ThemeIcon({ theme }: { theme: ThemeName }) {
  if (theme === "light") {
    return (
      <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.8" />
        <path
          d="M12 2.5v2M12 19.5v2M21.5 12h-2M4.5 12h-2M18.72 5.28l-1.42 1.42M6.7 17.3l-1.42 1.42M18.72 18.72l-1.42-1.42M6.7 6.7 5.28 5.28"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (theme === "dark") {
    return (
      <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24">
        <path
          d="M20.2 15.1A8.5 8.5 0 0 1 8.9 3.8 8.5 8.5 0 1 0 20.2 15.1Z"
          stroke="currentColor"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24">
      <rect height="12" rx="2" stroke="currentColor" strokeWidth="1.8" width="18" x="3" y="4" />
      <path d="M8 20h8M12 16v4" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
    </svg>
  );
}

export function ThemeSwitcher() {
  const [mounted, setMounted] = useState(false);
  const { setTheme, theme } = useTheme();

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return <span aria-hidden="true" className="inline-flex size-8" />;
  }

  const activeTheme: ThemeName = isThemeName(theme) ? theme : "system";
  const activeIndex = themes.indexOf(activeTheme);
  const nextTheme = themes[(activeIndex + 1) % themes.length];
  const activeLabel = activeTheme[0].toUpperCase() + activeTheme.slice(1);
  const nextLabel = nextTheme[0].toUpperCase() + nextTheme.slice(1);

  return (
    <Button
      aria-label={`Theme is ${activeLabel}. Change to ${nextLabel}.`}
      isIconOnly
      onPress={() => setTheme(nextTheme)}
      size="sm"
      variant="ghost"
    >
      <ThemeIcon theme={activeTheme} />
    </Button>
  );
}
