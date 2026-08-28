import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AuthStatus } from "@/components/auth/auth-provider";
import { StudySession } from "@/components/study/study-session";
import {
  createStudySession,
  getActiveStudySession,
  StudyApiError,
  submitRecallAnswer,
} from "@/lib/api/study";
import { savePendingAnswer } from "@/lib/study/pending-answer";
import {
  buildCompletedStudySession,
  buildStudyAnswerResponse,
  buildStudyItem,
  buildStudySession,
} from "@/test/study-builders";

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

const firstItem = buildStudyItem({
  id: "00000000-0000-4000-8000-000000000011",
  word_id: "00000000-0000-4000-8000-000000000012",
});

const secondItem = buildStudyItem({
  id: "00000000-0000-4000-8000-000000000013",
  position: 2,
  senses: [
    { ...firstItem.senses[0], definition: "Clear in expression.", example: "A lucid answer." },
  ],
  term: "lucid",
  word_id: "00000000-0000-4000-8000-000000000014",
});

const activeSession = buildStudySession({
  current_item: firstItem,
  id: "00000000-0000-4000-8000-000000000015",
  item_count: 2,
  items: [firstItem, secondItem],
  new_word_target: 2,
  planned_new_word_count: 2,
  remaining_count: 2,
});

const nextSession = buildStudySession({
  ...activeSession,
  answered_count: 1,
  current_item: secondItem,
  remaining_count: 1,
});

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
    submitRecallAnswerMock.mockResolvedValue(buildStudyAnswerResponse(nextSession));

    render(<StudySession />);

    expect(await screen.findByRole("heading", { name: "abate" })).toHaveFocus();
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
    expect(await screen.findByRole("heading", { name: "lucid" })).toHaveFocus();
    expect(screen.queryByText("Clear in expression.")).not.toBeInTheDocument();
  });

  it("announces a pending answer without offering a duplicate grade", async () => {
    let acceptAnswer: ((result: ReturnType<typeof buildStudyAnswerResponse>) => void) | undefined;
    getActiveStudySessionMock.mockResolvedValue(activeSession);
    submitRecallAnswerMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          acceptAnswer = resolve;
        }),
    );

    render(<StudySession />);

    await screen.findByRole("heading", { name: "abate" });
    fireEvent.click(screen.getByRole("button", { name: "Reveal meaning" }));
    fireEvent.click(screen.getByRole("button", { name: "Remembered" }));

    expect(screen.getByRole("status")).not.toBeEmptyDOMElement();
    expect(screen.getByRole("button", { name: "Remembered" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Forgot" })).toBeDisabled();

    acceptAnswer?.(buildStudyAnswerResponse(nextSession));
    expect(await screen.findByRole("heading", { name: "lucid" })).toBeInTheDocument();
  });

  it("retries a transient failure with the exact same client request identity", async () => {
    getActiveStudySessionMock.mockResolvedValue(activeSession);
    submitRecallAnswerMock
      .mockRejectedValueOnce(
        new StudyApiError("unavailable", "The database paused.", { retryable: true }),
      )
      .mockResolvedValueOnce(buildStudyAnswerResponse(nextSession));

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
    submitRecallAnswerMock.mockResolvedValue(buildStudyAnswerResponse(nextSession));

    render(<StudySession />);

    await waitFor(() => expect(submitRecallAnswerMock.mock.calls[0]?.[0]).toEqual(pending));
    expect(await screen.findByRole("heading", { name: "lucid" })).toBeInTheDocument();
    expect(window.sessionStorage.length).toBe(0);
  });

  it("clears a stale answer and resumes authoritative progress", async () => {
    getActiveStudySessionMock
      .mockResolvedValueOnce(activeSession)
      .mockResolvedValueOnce(nextSession);
    submitRecallAnswerMock.mockRejectedValue(
      new StudyApiError("conflict", "Stale answer.", { code: "study_item_out_of_order" }),
    );

    render(<StudySession />);

    await screen.findByRole("heading", { name: "abate" });
    fireEvent.click(screen.getByRole("button", { name: "Reveal meaning" }));
    fireEvent.click(screen.getByRole("button", { name: "Remembered" }));

    expect(await screen.findByRole("heading", { name: "lucid" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).not.toBeEmptyDOMElement();
    expect(window.sessionStorage.length).toBe(0);
  });

  it("offers authoritative reload when stale progress cannot be refreshed immediately", async () => {
    getActiveStudySessionMock
      .mockResolvedValueOnce(activeSession)
      .mockRejectedValueOnce(
        new StudyApiError("unavailable", "Study is temporarily unavailable.", {
          retryable: true,
        }),
      )
      .mockResolvedValueOnce(nextSession);
    submitRecallAnswerMock.mockRejectedValue(
      new StudyApiError("conflict", "Stale answer.", { code: "study_item_out_of_order" }),
    );

    render(<StudySession />);

    await screen.findByRole("heading", { name: "abate" });
    fireEvent.click(screen.getByRole("button", { name: "Reveal meaning" }));
    fireEvent.click(screen.getByRole("button", { name: "Remembered" }));

    expect(await screen.findByRole("button", { name: "Restore again" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remembered" })).not.toBeInTheDocument();
    expect(submitRecallAnswerMock).toHaveBeenCalledOnce();

    fireEvent.click(screen.getByRole("button", { name: "Restore again" }));
    expect(await screen.findByRole("heading", { name: "lucid" })).toBeInTheDocument();
    expect(submitRecallAnswerMock).toHaveBeenCalledOnce();
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
      .mockResolvedValueOnce(buildStudyAnswerResponse(nextSession));

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

  it("celebrates only an explicitly completed session", async () => {
    getActiveStudySessionMock.mockResolvedValue(buildCompletedStudySession());

    render(<StudySession />);

    expect(await screen.findByRole("heading", { name: "Session complete" })).toBeInTheDocument();
  });

  it("lets the learner leave an abandoned session and plan another", async () => {
    getActiveStudySessionMock.mockResolvedValue(
      buildStudySession({ current_item: null, status: "abandoned" }),
    );

    render(<StudySession />);

    expect(await screen.findByRole("heading", { name: "Session ended" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Plan another session" }));
    expect(screen.getByRole("heading", { name: "Start a focused session" })).toBeInTheDocument();
  });

  it("recovers an active session that has no current item", async () => {
    const malformedActiveSession = buildStudySession({
      current_item: null,
      item_count: 1,
      remaining_count: 1,
    });
    getActiveStudySessionMock
      .mockResolvedValueOnce(malformedActiveSession)
      .mockResolvedValueOnce(activeSession);

    render(<StudySession />);

    expect(
      await screen.findByRole("heading", { name: "Study session needs attention" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reload study progress" }));
    expect(await screen.findByRole("heading", { name: "abate" })).toBeInTheDocument();
  });

  it("redirects an unauthenticated learner without loading study state", async () => {
    auth.status = "unauthenticated";

    render(<StudySession />);

    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/sign-in"));
    expect(screen.getByRole("status")).not.toBeEmptyDOMElement();
    expect(getActiveStudySessionMock).not.toHaveBeenCalled();
  });
});
