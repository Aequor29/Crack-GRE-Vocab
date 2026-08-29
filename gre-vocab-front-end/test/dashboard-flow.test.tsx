import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AuthStatus } from "@/components/auth/auth-provider";
import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import type { Account } from "@/lib/api/auth";

const navigation = vi.hoisted(() => ({ replace: vi.fn() }));
const auth = vi.hoisted(() => ({
  account: { display_name: "Ada", email: "ada@example.com", id: 7 } as Account | null,
  refresh: vi.fn(),
  status: "authenticated" as AuthStatus,
}));

vi.mock("next/navigation", () => ({ useRouter: () => navigation }));
vi.mock("@/components/auth/auth-provider", () => ({ useAuth: () => auth }));

describe("dashboard shell", () => {
  afterEach(cleanup);

  beforeEach(() => {
    auth.account = { display_name: "Ada", email: "ada@example.com", id: 7 };
    auth.status = "authenticated";
    auth.refresh.mockReset();
    navigation.replace.mockReset();
  });

  it("gives an authenticated learner a direct path into study", () => {
    render(<DashboardShell />);

    expect(screen.getByRole("heading", { level: 1, name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByText(/Welcome back,/)).toHaveTextContent("Welcome back, Ada");
    expect(screen.getByRole("link", { name: "Start studying" })).toHaveAttribute("href", "/study");
    expect(screen.getByRole("link", { name: "Manage account" })).toHaveAttribute(
      "href",
      "/account",
    );
  });

  it("redirects an unauthenticated learner to sign in", async () => {
    auth.account = null;
    auth.status = "unauthenticated";

    render(<DashboardShell />);

    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/sign-in"));
  });

  it("offers recovery when the local backend is unavailable", () => {
    auth.account = null;
    auth.status = "unavailable";

    render(<DashboardShell />);

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(auth.refresh).toHaveBeenCalledOnce();
  });
});
