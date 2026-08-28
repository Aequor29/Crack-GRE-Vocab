import { afterEach, describe, expect, it, vi } from "vitest";

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
import {
  buildCompletedStudySession,
  buildStudyAnswerResponse,
  buildStudyItem,
  buildStudySession,
} from "@/test/study-builders";

const item = buildStudyItem();

const session = buildStudySession({
  current_item: item,
  items: [item],
});

const answerResponse = buildStudyAnswerResponse(
  buildCompletedStudySession({
    items: [item],
    planned_new_word_count: 1,
  }),
);

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

  it("rejects malformed nested session content before the study UI can dereference it", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const malformedSession = {
      ...session,
      current_item: {
        ...item,
        senses: [{ ...item.senses[0], definition: 42 }],
      },
    };
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(malformedSession, 200));

    await expect(getActiveStudySession({ fetcher })).rejects.toMatchObject({
      kind: "unavailable",
    } satisfies Partial<StudyApiError>);
  });

  it.each([
    {
      label: "the current example",
      payload: {
        ...answerResponse,
        session: {
          ...answerResponse.session,
          current_item: {
            ...item,
            senses: [{ ...item.senses[0], example: null }],
          },
        },
      },
    },
    {
      label: "the scheduling outcome",
      payload: {
        ...answerResponse,
        outcome: { ...answerResponse.outcome, next_due_at: null },
      },
    },
  ])("rejects an answer response with malformed $label", async ({ payload }) => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "answer-token" }, 200))
      .mockResolvedValueOnce(jsonResponse(payload, 201));

    await expect(
      submitRecallAnswer(
        {
          client_request_id: "00000000-0000-4000-8000-000000000004",
          itemId: item.id,
          rating: "remembered",
          sessionId: session.id,
        },
        { fetcher },
      ),
    ).rejects.toMatchObject({ kind: "unavailable" } satisfies Partial<StudyApiError>);
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
    const offlineFetcher = vi.fn<typeof fetch>().mockRejectedValue(new TypeError("offline"));

    await expect(getActiveStudySession({ fetcher: expiredLoginFetcher })).rejects.toMatchObject({
      kind: "unauthenticated",
      retryable: false,
    } satisfies Partial<StudyApiError>);
    await expect(createStudySession(1, { fetcher: rejectedCsrfFetcher })).rejects.toMatchObject({
      kind: "csrf",
      retryable: true,
    } satisfies Partial<StudyApiError>);
    await expect(getActiveStudySession({ fetcher: offlineFetcher })).rejects.toMatchObject({
      kind: "unavailable",
      retryable: true,
    } satisfies Partial<StudyApiError>);
  });

  it.each([
    {
      code: "study_item_out_of_order",
      expectedKind: "conflict",
      expectedRetryable: false,
      status: 409,
    },
    {
      code: "study_temporarily_unavailable",
      expectedKind: "unavailable",
      expectedRetryable: true,
      status: 503,
    },
  ] as const)(
    "maps $code without exposing backend prose",
    async ({ code, expectedKind, expectedRetryable, status }) => {
      vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
      const fetcher = vi
        .fn<typeof fetch>()
        .mockResolvedValueOnce(jsonResponse({ csrf_token: "error-token" }, 200))
        .mockResolvedValueOnce(
          jsonResponse({ code, detail: "Framework wording changed.", retryable: true }, status),
        );

      const request = createStudySession(1, { fetcher });
      await expect(request).rejects.toMatchObject({
        code,
        kind: expectedKind,
        retryable: expectedRetryable,
      } satisfies Partial<StudyApiError>);
      await expect(request).rejects.not.toMatchObject({ message: "Framework wording changed." });
    },
  );

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
