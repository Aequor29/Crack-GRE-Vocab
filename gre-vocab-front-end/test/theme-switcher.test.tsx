import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ThemeSwitcher } from "@/components/theme-switcher";

const theme = vi.hoisted(() => ({ setTheme: vi.fn(), value: "light" }));

vi.mock("next-themes", () => ({
  useTheme: () => ({ setTheme: theme.setTheme, theme: theme.value }),
}));

describe("theme switcher", () => {
  it("shows an accessible icon button and advances to the next theme", () => {
    render(<ThemeSwitcher />);

    const button = screen.getByRole("button", {
      name: "Theme is Light. Change to Dark.",
    });
    expect(button).not.toHaveTextContent(/\S/);
    expect(button.querySelector("svg")).toBeInTheDocument();

    fireEvent.click(button);

    expect(theme.setTheme).toHaveBeenCalledWith("dark");
  });
});
