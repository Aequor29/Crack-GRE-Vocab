import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import HomePage from "@/app/page";
import { SiteHeader } from "@/components/site-header";

vi.mock("@/components/auth/auth-navigation", () => ({
  AuthNavigation: () => <a href="/sign-in">Sign in</a>,
}));

describe("application shell", () => {
  it("renders the primary navigation and page landmark", () => {
    render(
      <>
        <SiteHeader />
        <HomePage />
      </>,
    );

    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Crack GRE Vocab home" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Rebuild status" })).toHaveAttribute(
      "href",
      "/#status",
    );
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Build recall that lasts.");
  });
});
