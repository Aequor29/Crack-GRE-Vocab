import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AuthStatus } from "@/components/auth/auth-provider";
import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import type { Account } from "@/lib/api/auth";
import type { LearningInsights } from "@/lib/api/generated/schema.generated";
import { ProgressApiError } from "@/lib/api/progress";
import { learningInsights, learningProgress } from "./progress-builders";

const navigation = vi.hoisted(() => ({ replace: vi.fn() }));
const auth = vi.hoisted(() => ({
  account: { display_name: "Ada", email: "ada@example.com", id: 7 } as Account | null,
  refresh: vi.fn(),
  status: "authenticated" as AuthStatus,
}));
const progressApi = vi.hoisted(() => ({
  getLearningInsights: vi.fn(),
  getLearningProgress: vi.fn(),
}));

const progress = learningProgress();
const insights = learningInsights();

const emptyInsights: LearningInsights = {
  ...insights,
  review_recall: {
    current: {
      ...insights.review_recall.current,
      remembered: 0,
      answers: 0,
      rate_percent: null,
      has_sufficient_data: false,
    },
    previous: {
      ...insights.review_recall.previous,
      remembered: 0,
      answers: 0,
      rate_percent: null,
      has_sufficient_data: false,
    },
    change_percentage_points: null,
  },
  consistency: { ...insights.consistency, current_streak_days: 0, study_days: [] },
  learning_curve: insights.learning_curve.map((week) => ({
    ...week,
    unseen: 3034,
    learning: 0,
    reviewing: 0,
    mastered: 0,
  })),
};

vi.mock("next/navigation", () => ({ useRouter: () => navigation }));
vi.mock("@/components/auth/auth-provider", () => ({ useAuth: () => auth }));
vi.mock("@/lib/api/progress", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/progress")>()),
  getLearningInsights: progressApi.getLearningInsights,
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
    progressApi.getLearningInsights.mockReset();
    progressApi.getLearningInsights.mockResolvedValue(insights);
  });

  it("shows learning progress, recall trends, and the next study action", async () => {
    render(<DashboardShell />);

    expect(screen.getByRole("heading", { level: 1, name: "Dashboard" })).toBeInTheDocument();
    expect(await screen.findByText("Learning progress")).toBeInTheDocument();
    expect(screen.getByText("34 of 3,034 words seen")).toBeInTheDocument();
    expect(screen.getByText("Reviewing").closest("div")).toHaveTextContent("Reviewing9");
    expect(screen.getByText("Mastered").closest("div")).toHaveTextContent("Mastered5");
    expect(screen.getByText("11 due today")).toBeInTheDocument();
    expect(screen.getByText("8 answers")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Continue studying" })).toHaveAttribute(
      "href",
      "/study",
    );
    expect(screen.getByRole("link", { name: "Manage account" })).toHaveAttribute(
      "href",
      "/account",
    );
    expect(await screen.findByRole("heading", { name: "Review recall" })).toBeInTheDocument();
    expect(screen.getByText("80%")).toBeInTheDocument();
    expect(screen.getByText("+20 points from the previous 7 days")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Learning curve" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Study days" })).toBeInTheDocument();
    expect(screen.getByText("3 day streak")).toBeInTheDocument();
    expect(
      screen.getByLabelText("August 29, 2026: 4 words practiced across 5 answers"),
    ).toBeInTheDocument();
  });

  it("offers a new learner their first study session", async () => {
    progressApi.getLearningProgress.mockResolvedValue({
      ...progress,
      corpus: { ...progress.corpus, unseen: 3034, learning: 0, reviewing: 0, mastered: 0 },
      actionable: { due_now: 0, due_today: 0, has_active_session: false },
      today: {
        ...progress.today,
        sessions_started: 0,
        answers: 0,
        remembered: 0,
        forgot: 0,
      },
    });
    progressApi.getLearningInsights.mockResolvedValue(emptyInsights);

    render(<DashboardShell />);

    expect(await screen.findByText("0 of 3,034 words seen")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Start studying" })).toHaveAttribute("href", "/study");
    expect(await screen.findByText("No review history yet")).toBeInTheDocument();
    expect(screen.getByText("0 day streak")).toBeInTheDocument();
  });

  it("keeps current progress usable when historical insights are unavailable", async () => {
    progressApi.getLearningInsights.mockRejectedValueOnce(
      new ProgressApiError("unavailable", "Unavailable", { retryable: true }),
    );

    render(<DashboardShell />);

    expect(await screen.findByText("34 of 3,034 words seen")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).not.toBeEmptyDOMElement();
    progressApi.getLearningInsights.mockResolvedValueOnce(insights);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "Review recall" })).toBeInTheDocument();
  });

  it("announces progress loading and offers a focused retry", async () => {
    progressApi.getLearningProgress.mockRejectedValueOnce(
      new ProgressApiError("unavailable", "Unavailable", { retryable: true }),
    );

    render(<DashboardShell />);

    expect(screen.getByRole("status", { name: "Loading your progress" })).toBeInTheDocument();
    expect(await screen.findByRole("alert")).not.toBeEmptyDOMElement();
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
