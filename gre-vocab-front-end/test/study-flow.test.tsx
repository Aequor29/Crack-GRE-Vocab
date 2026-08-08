import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AuthStatus } from "@/components/auth/auth-provider";
import { StudySession } from "@/components/study/study-session";
import type {
  StudyAnswerResponse,
  StudySession as StudySessionContract,
} from "@/lib/api/generated/schema.generated";
import {
  createStudySession,
  getActiveStudySession,
  StudyApiError,
  submitRecallAnswer,
} from "@/lib/api/study";
import { savePendingAnswer } from "@/lib/study/pending-answer";

const navigation = vi.hoisted(() => ({ replace: vi.fn() }));
const auth = vi.hoisted(() => ({
  account: { display_name: "Ada", email: "ada@example.com", id: 7 },
  refresh: vi.fn(),
  signIn: vi.fn(),
  signOut: vi.fn(),
  signUp: vi.fn(),
  status: "authenticated" as AuthStatus,
}));

vi.mock("next/navigation", () => ({ useRouter: () => navigation }));
vi.mock("@/components/auth/auth-provider", () => ({ useAuth: () => auth }));
vi.mock("@/lib/api/study", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/study")>();
  return {
    ...actual,
    createStudySession: vi.fn(),
    getActiveStudySession: vi.fn(),
    submitRecallAnswer: vi.fn(),
  };
});

const firstItem = {
  id: "00000000-0000-4000-8000-000000000011",
  kind: "new" as const,
  position: 1,
  pronunciation: "/abate/",
  senses: [
    {
      definition: "To become less intense.",
      example: "The storm began to abate.",
      part_of_speech: "verb",
      position: 1,
    },
  ],
  term: "abate",
  word_id: "00000000-0000-4000-8000-000000000012",
};

const secondItem = {
  ...firstItem,
  id: "00000000-0000-4000-8000-000000000013",
  position: 2,
  senses: [
    { ...firstItem.senses[0], definition: "Clear in expression.", example: "A lucid answer." },
  ],
  term: "lucid",
  word_id: "00000000-0000-4000-8000-000000000014",
};

const activeSession: StudySessionContract = {
  answered_count: 0,
  corpus_version: "m1-v1",
  created_at: "2026-08-07T05:00:00Z",
  current_item: firstItem,
  id: "00000000-0000-4000-8000-000000000015",
  item_count: 2,
  items: [firstItem, secondItem],
  new_word_target: 2,
  planned_new_word_count: 2,
  planner_version: "m1-due-first-v1",
  remaining_count: 2,
  status: "active",
};

const nextSession: StudySessionContract = {
  ...activeSession,
  answered_count: 1,
  current_item: secondItem,
  remaining_count: 1,
};

function response(session: StudySessionContract): StudyAnswerResponse {
  return {
    answer: {
      accepted_at: "2026-08-07T05:01:00Z",
      client_request_id: "00000000-0000-4000-8000-000000000016",
      id: "00000000-0000-4000-8000-000000000017",
      item_id: firstItem.id,
      rating: "remembered",
      submitted_at: "2026-08-07T05:01:00Z",
    },
    outcome: {
      id: "00000000-0000-4000-8000-000000000018",
      next_due_at: "2026-08-07T05:11:00Z",
      next_phase: "learning",
      occurred_at: "2026-08-07T05:01:00Z",
      previous_phase: "",
      review_number: 1,
      scheduler_version: "m1-fsrs-6.3.1-binary-v1",
    },
    replayed: false,
    session,
  };
}

const createStudySessionMock = vi.mocked(createStudySession);
const getActiveStudySessionMock = vi.mocked(getActiveStudySession);
const submitRecallAnswerMock = vi.mocked(submitRecallAnswer);

describe("study session experience", () => {
  afterEach(cleanup);

  beforeEach(() => {
    window.sessionStorage.clear();
    auth.status = "authenticated";
    navigation.replace.mockReset();
    auth.refresh.mockReset();
    createStudySessionMock.mockReset();
    getActiveStudySessionMock.mockReset();
    submitRecallAnswerMock.mockReset();
  });

  it("shows backend recovery when authentication cannot be checked", async () => {
    auth.status = "unavailable";

    render(<StudySession />);

    expect(screen.getByRole("alert")).toHaveTextContent("backend is unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(auth.refresh).toHaveBeenCalledTimes(1));
    expect(getActiveStudySessionMock).not.toHaveBeenCalled();
  });

  it("keeps definitions hidden until reveal and advances only after acceptance", async () => {
    getActiveStudySessionMock.mockResolvedValue(activeSession);
    submitRecallAnswerMock.mockResolvedValue(response(nextSession));

    render(<StudySession />);

    expect(await screen.findByRole("heading", { name: "abate" })).toBeInTheDocument();
    expect(screen.queryByText("To become less intense.")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reveal meaning" }));
    expect(screen.getByText("To become less intense.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Remembered" }));
    await waitFor(() => expect(submitRecallAnswerMock).toHaveBeenCalledTimes(1));
    const submitted = submitRecallAnswerMock.mock.calls[0][0];
    expect(submitted).toMatchObject({
      itemId: firstItem.id,
      rating: "remembered",
      sessionId: activeSession.id,
    });
    expect(submitted.client_request_id).toEqual(expect.any(String));
    expect(await screen.findByRole("heading", { name: "lucid" })).toBeInTheDocument();
    expect(screen.queryByText("Clear in expression.")).not.toBeInTheDocument();
  });

  it("retries a transient failure with the exact same client request identity", async () => {
    getActiveStudySessionMock.mockResolvedValue(activeSession);
    submitRecallAnswerMock
      .mockRejectedValueOnce(
        new StudyApiError("unavailable", "The database paused.", { retryable: true }),
      )
      .mockResolvedValueOnce(response(nextSession));

    render(<StudySession />);

    await screen.findByRole("heading", { name: "abate" });
    fireEvent.click(screen.getByRole("button", { name: "Reveal meaning" }));
    fireEvent.click(screen.getByRole("button", { name: "Forgot" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("database paused");
    const firstOperation = submitRecallAnswerMock.mock.calls[0][0];
    fireEvent.click(screen.getByRole("button", { name: "Retry the same answer" }));

    await waitFor(() => expect(submitRecallAnswerMock).toHaveBeenCalledTimes(2));
    expect(submitRecallAnswerMock.mock.calls[1][0]).toEqual(firstOperation);
    expect(await screen.findByRole("heading", { name: "lucid" })).toBeInTheDocument();
    expect(window.sessionStorage.length).toBe(0);
  });

  it("refreshes expired authentication without discarding the pending answer", async () => {
    getActiveStudySessionMock.mockResolvedValue(activeSession);
    submitRecallAnswerMock.mockRejectedValue(
      new StudyApiError("unauthenticated", "Your sign-in expired."),
    );

    render(<StudySession />);

    await screen.findByRole("heading", { name: "abate" });
    fireEvent.click(screen.getByRole("button", { name: "Reveal meaning" }));
    fireEvent.click(screen.getByRole("button", { name: "Remembered" }));

    await waitFor(() => expect(auth.refresh).toHaveBeenCalledTimes(1));
    expect(window.sessionStorage.length).toBe(1);
    expect(submitRecallAnswerMock).toHaveBeenCalledTimes(1);
  });

  it("replays a stored pending answer before restoring session progress", async () => {
    const pending = savePendingAnswer(7, {
      client_request_id: "00000000-0000-4000-8000-000000000019",
      itemId: firstItem.id,
      rating: "remembered",
      sessionId: activeSession.id,
    });
    submitRecallAnswerMock.mockResolvedValue(response(nextSession));

    render(<StudySession />);

    await waitFor(() =>
      expect(submitRecallAnswerMock).toHaveBeenCalledWith(pending, {
        signal: expect.any(AbortSignal),
      }),
    );
    expect(getActiveStudySessionMock).not.toHaveBeenCalled();
    expect(await screen.findByRole("heading", { name: "lucid" })).toBeInTheDocument();
    expect(window.sessionStorage.length).toBe(0);
  });

  it("offers only exact retry after a saved answer fails to restore", async () => {
    const pending = savePendingAnswer(7, {
      client_request_id: "00000000-0000-4000-8000-000000000020",
      itemId: firstItem.id,
      rating: "forgot",
      sessionId: activeSession.id,
    });
    submitRecallAnswerMock
      .mockRejectedValueOnce(
        new StudyApiError("unavailable", "The database paused.", { retryable: true }),
      )
      .mockResolvedValueOnce(response(nextSession));

    render(<StudySession />);

    expect(await screen.findByRole("alert")).toHaveTextContent("database paused");
    expect(screen.queryByRole("button", { name: "Start session" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry saved answer" }));

    await waitFor(() => expect(submitRecallAnswerMock).toHaveBeenCalledTimes(2));
    expect(submitRecallAnswerMock.mock.calls[1][0]).toEqual(pending);
    expect(await screen.findByRole("heading", { name: "lucid" })).toBeInTheDocument();
    expect(window.sessionStorage.length).toBe(0);
  });

  it("offers session planning when no active session can be restored", async () => {
    getActiveStudySessionMock.mockResolvedValue(null);
    createStudySessionMock.mockResolvedValue(activeSession);

    render(<StudySession />);

    expect(
      await screen.findByRole("heading", { name: "Start a focused session" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Recall each word first/)).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: /new-word target/i })).toHaveValue("10");
    fireEvent.click(screen.getByRole("button", { name: "Start session" }));

    await waitFor(() => expect(createStudySessionMock).toHaveBeenCalledWith(10));
    expect(await screen.findByRole("heading", { name: "abate" })).toBeInTheDocument();
  });
});
