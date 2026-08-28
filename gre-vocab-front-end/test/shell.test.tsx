import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import HomePage from "@/app/page";
import { SiteHeader } from "@/components/site-header";

const navigation = vi.hoisted(() => ({ redirect: vi.fn() }));

vi.mock("next/navigation", () => ({ redirect: navigation.redirect }));
describe("application shell", () => {
  it("keeps only dashboard and study in primary navigation", () => {
    render(<SiteHeader />);

    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Crack GRE Vocab home" })).toHaveAttribute(
      "href",
      "/dashboard",
    );
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/dashboard");
    expect(screen.getByRole("link", { name: "Study" })).toHaveAttribute("href", "/study");
    expect(screen.queryByRole("link", { name: "Rebuild status" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Principles" })).not.toBeInTheDocument();
  });

  it("routes the root page to the dashboard", () => {
    HomePage();

    expect(navigation.redirect).toHaveBeenCalledWith("/dashboard");
  });
});
