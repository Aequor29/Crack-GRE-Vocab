"use client";

import { Button } from "@heroui/react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

const themes = ["system", "light", "dark"] as const;

type ThemeName = (typeof themes)[number];

function isThemeName(value: string | undefined): value is ThemeName {
  return themes.some((theme) => theme === value);
}

export function ThemeSwitcher() {
  const [mounted, setMounted] = useState(false);
  const { setTheme, theme } = useTheme();

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <span aria-hidden="true" className="inline-flex h-8 w-24 items-center justify-center">
        Theme
      </span>
    );
  }

  const activeTheme: ThemeName = isThemeName(theme) ? theme : "system";
  const activeIndex = themes.indexOf(activeTheme);
  const nextTheme = themes[(activeIndex + 1) % themes.length];
  const activeLabel = activeTheme[0].toUpperCase() + activeTheme.slice(1);
  const nextLabel = nextTheme[0].toUpperCase() + nextTheme.slice(1);

  return (
    <Button
      aria-label={`Theme is ${activeLabel}. Change to ${nextLabel}.`}
      onPress={() => setTheme(nextTheme)}
      size="sm"
      variant="ghost"
    >
      Theme: {activeLabel}
    </Button>
  );
}
