import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import HomePage from "@/app/page";
import { SiteHeader } from "@/components/site-header";

const navigation = vi.hoisted(() => ({ redirect: vi.fn() }));

vi.mock("next/navigation", () => ({ redirect: navigation.redirect }));
describe("application shell", () => {
  it("offers dashboard and study as the complete primary navigation", () => {
    render(<SiteHeader />);

    const primaryNavigation = screen.getByRole("navigation", { name: "Primary" });
    expect(within(primaryNavigation).getAllByRole("link")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Crack GRE Vocab home" })).toHaveAttribute(
      "href",
      "/dashboard",
    );
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/dashboard");
    expect(screen.getByRole("link", { name: "Study" })).toHaveAttribute("href", "/study");
  });

  it("routes the root page to the dashboard", () => {
    HomePage();

    expect(navigation.redirect).toHaveBeenCalledWith("/dashboard");
  });
});
