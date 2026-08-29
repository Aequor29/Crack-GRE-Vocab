import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AuthStatus } from "@/components/auth/auth-provider";
import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import type { Account } from "@/lib/api/auth";
import type { LearningProgressSummary } from "@/lib/api/generated/schema.generated";
import { ProgressApiError } from "@/lib/api/progress";

const navigation = vi.hoisted(() => ({ replace: vi.fn() }));
const auth = vi.hoisted(() => ({
  account: { display_name: "Ada", email: "ada@example.com", id: 7 } as Account | null,
  refresh: vi.fn(),
  status: "authenticated" as AuthStatus,
}));
const progressApi = vi.hoisted(() => ({ getLearningProgress: vi.fn() }));

const progress: LearningProgressSummary = {
  corpus: {
    version: "m1-v2",
    total: 3034,
    unseen: 3000,
    learning: 20,
    review: 14,
  },
  actionable: {
    due_now: 7,
    due_today: 11,
    has_active_session: true,
  },
  today: {
    date: "2026-08-28",
    timezone: "America/Chicago",
    sessions_started: 1,
    sessions_completed: 0,
    answers: 8,
    remembered: 6,
    forgot: 2,
  },
};

vi.mock("next/navigation", () => ({ useRouter: () => navigation }));
vi.mock("@/components/auth/auth-provider", () => ({ useAuth: () => auth }));
vi.mock("@/lib/api/progress", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/progress")>()),
  getLearningProgress: progressApi.getLearningProgress,
}));

describe("dashboard shell", () => {
  afterEach(cleanup);

  beforeEach(() => {
    auth.account = { display_name: "Ada", email: "ada@example.com", id: 7 };
    auth.status = "authenticated";
    auth.refresh.mockReset();
    navigation.replace.mockReset();
    progressApi.getLearningProgress.mockReset();
    progressApi.getLearningProgress.mockResolvedValue(progress);
  });

  it("shows actionable coverage and today's work without recall clutter", async () => {
    render(<DashboardShell />);

    expect(screen.getByRole("heading", { level: 1, name: "Dashboard" })).toBeInTheDocument();
    expect(await screen.findByText("34 of 3,034 words seen")).toBeInTheDocument();
    expect(screen.getByText("11 due today")).toBeInTheDocument();
    expect(screen.getByText("8 answers")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Recent recall" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Continue studying" })).toHaveAttribute(
      "href",
      "/study",
    );
    expect(screen.getByRole("link", { name: "Manage account" })).toHaveAttribute(
      "href",
      "/account",
    );
  });

  it("gives a new learner a clear first action without fake history", async () => {
    progressApi.getLearningProgress.mockResolvedValue({
      ...progress,
      corpus: { ...progress.corpus, unseen: 3034, learning: 0, review: 0 },
      actionable: { due_now: 0, due_today: 0, has_active_session: false },
      today: {
        ...progress.today,
        sessions_started: 0,
        answers: 0,
        remembered: 0,
        forgot: 0,
      },
    });

    render(<DashboardShell />);

    expect(await screen.findByText("0 of 3,034 words seen")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Recent recall" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Start studying" })).toHaveAttribute("href", "/study");
  });

  it("announces progress loading and offers a focused retry", async () => {
    progressApi.getLearningProgress.mockRejectedValueOnce(
      new ProgressApiError("unavailable", "Unavailable", { retryable: true }),
    );

    render(<DashboardShell />);

    expect(screen.getByRole("status", { name: "Loading your progress" })).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("We couldn't load your progress.");
    progressApi.getLearningProgress.mockResolvedValueOnce(progress);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("34 of 3,034 words seen")).toBeInTheDocument();
  });

  it("redirects an unauthenticated learner to sign in", async () => {
    auth.account = null;
    auth.status = "unauthenticated";

    render(<DashboardShell />);

    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/sign-in"));
    expect(progressApi.getLearningProgress).not.toHaveBeenCalled();
  });

  it("offers recovery when the dashboard cannot load", () => {
    auth.account = null;
    auth.status = "unavailable";

    render(<DashboardShell />);

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(auth.refresh).toHaveBeenCalledOnce();
  });
});
