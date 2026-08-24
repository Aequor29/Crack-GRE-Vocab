import { afterEach, describe, expect, it, vi } from "vitest";

import type { StudyAnswerResponse, StudySession } from "@/lib/api/generated/schema.generated";
import {
  createStudySession,
  getActiveStudySession,
  type StudyApiError,
  submitRecallAnswer,
} from "@/lib/api/study";
import {
  clearPendingAnswer,
  loadPendingAnswer,
  savePendingAnswer,
} from "@/lib/study/pending-answer";

const item = {
  id: "00000000-0000-4000-8000-000000000001",
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
  word_id: "00000000-0000-4000-8000-000000000002",
};

const session: StudySession = {
  answered_count: 0,
  corpus_version: "m1-v1",
  created_at: "2026-08-07T05:00:00Z",
  current_item: item,
  id: "00000000-0000-4000-8000-000000000003",
  item_count: 1,
  items: [item],
  new_word_target: 1,
  planned_new_word_count: 1,
  planner_version: "m1-due-first-v1",
  remaining_count: 1,
  status: "active",
};

const answerResponse: StudyAnswerResponse = {
  answer: {
    accepted_at: "2026-08-07T05:01:00Z",
    client_request_id: "00000000-0000-4000-8000-000000000004",
    id: "00000000-0000-4000-8000-000000000005",
    item_id: item.id,
    rating: "remembered",
    submitted_at: "2026-08-07T05:01:00Z",
  },
  outcome: {
    id: "00000000-0000-4000-8000-000000000006",
    next_due_at: "2026-08-07T05:11:00Z",
    next_phase: "learning",
    occurred_at: "2026-08-07T05:01:00Z",
    previous_phase: "",
    review_number: 1,
    scheduler_version: "m1-fsrs-6.3.1-binary-v1",
  },
  replayed: false,
  session: {
    ...session,
    answered_count: 1,
    current_item: null,
    ended_at: "2026-08-07T05:01:00Z",
    remaining_count: 0,
    status: "completed",
  },
};

const jsonResponse = (body: unknown, status: number) =>
  new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });

describe("study API client", () => {
  afterEach(() => {
    clearPendingAnswer();
    vi.unstubAllEnvs();
  });

  it("restores an active credentialed session and treats 404 as no active work", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const activeFetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(session, 200));
    const emptyFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ detail: "none" }, 404));

    await expect(getActiveStudySession({ fetcher: activeFetcher })).resolves.toEqual(session);
    await expect(getActiveStudySession({ fetcher: emptyFetcher })).resolves.toBeNull();
    expect(activeFetcher).toHaveBeenCalledWith(
      "http://localhost:8000/api/study/sessions/active/",
      expect.objectContaining({ credentials: "include", method: "GET" }),
    );
  });

  it("creates a session only after obtaining a fresh CSRF token", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "study-token" }, 200))
      .mockResolvedValueOnce(jsonResponse(session, 201));

    await expect(createStudySession(1, { fetcher })).resolves.toEqual(session);
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/study/sessions/",
      expect.objectContaining({
        body: JSON.stringify({ new_word_target: 1 }),
        credentials: "include",
        headers: expect.objectContaining({ "X-CSRFToken": "study-token" }),
        method: "POST",
      }),
    );
  });

  it("submits the exact request identity and exposes retryable persistence failures", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const input = {
      client_request_id: "00000000-0000-4000-8000-000000000004",
      itemId: item.id,
      rating: "remembered" as const,
      sessionId: session.id,
    };
    const acceptedFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "answer-token" }, 200))
      .mockResolvedValueOnce(jsonResponse(answerResponse, 201));
    const failedFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "retry-token" }, 200))
      .mockResolvedValueOnce(
        jsonResponse({ detail: "Persistence interrupted.", retryable: true }, 503),
      );

    await expect(submitRecallAnswer(input, { fetcher: acceptedFetcher })).resolves.toEqual(
      answerResponse,
    );
    expect(acceptedFetcher).toHaveBeenNthCalledWith(
      2,
      `http://localhost:8000/api/study/sessions/${session.id}/items/${item.id}/answer/`,
      expect.objectContaining({
        body: JSON.stringify({
          client_request_id: input.client_request_id,
          rating: "remembered",
        }),
      }),
    );
    await expect(submitRecallAnswer(input, { fetcher: failedFetcher })).rejects.toMatchObject({
      kind: "unavailable",
      retryable: true,
    } satisfies Partial<StudyApiError>);
  });

  it("distinguishes an expired login from a rejected CSRF token", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const expiredLoginFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        jsonResponse({ detail: "Authentication credentials were not provided." }, 403),
      );
    const rejectedCsrfFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "stale-token" }, 200))
      .mockResolvedValueOnce(
        jsonResponse({ code: "csrf_failed", detail: "Request proof rejected." }, 403),
      );

    await expect(getActiveStudySession({ fetcher: expiredLoginFetcher })).rejects.toMatchObject({
      kind: "unauthenticated",
      retryable: false,
    } satisfies Partial<StudyApiError>);
    await expect(createStudySession(1, { fetcher: rejectedCsrfFetcher })).rejects.toMatchObject({
      kind: "csrf",
      retryable: true,
    } satisfies Partial<StudyApiError>);
  });

  it("keeps only a valid versioned pending answer for the current learner", () => {
    const input = {
      client_request_id: "00000000-0000-4000-8000-000000000004",
      itemId: item.id,
      rating: "forgot" as const,
      sessionId: session.id,
    };

    const pending = savePendingAnswer(7, input);

    expect(loadPendingAnswer(7)).toEqual(pending);
    expect(loadPendingAnswer(8)).toBeNull();
    expect(loadPendingAnswer(7)).toBeNull();
  });
});
