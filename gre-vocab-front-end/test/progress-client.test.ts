import { afterEach, describe, expect, it, vi } from "vitest";
import type { LearningProgressSummary } from "@/lib/api/generated/schema.generated";
import { getLearningProgress, type ProgressApiError } from "@/lib/api/progress";

const summary: LearningProgressSummary = {
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
  recent_outcomes: [
    {
      word_id: "00000000-0000-4000-8000-000000000001",
      term: "abate",
      rating: "remembered",
      phase: "learning",
      next_due_at: "2026-08-28T18:10:00Z",
      occurred_at: "2026-08-28T18:00:00Z",
    },
  ],
};

const jsonResponse = (body: unknown, status: number) =>
  new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });

describe("progress API client", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("loads a validated summary for the requested IANA timezone", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(summary, 200));

    await expect(getLearningProgress("America/Chicago", { fetcher })).resolves.toEqual(summary);
    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:8000/api/progress/summary/?timezone=America%2FChicago",
      expect.objectContaining({ credentials: "include", method: "GET" }),
    );
  });

  it("rejects malformed nested progress before the dashboard renders it", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        jsonResponse({ ...summary, corpus: { ...summary.corpus, total: -1 } }, 200),
      );

    await expect(getLearningProgress("America/Chicago", { fetcher })).rejects.toMatchObject({
      kind: "unavailable",
    } satisfies Partial<ProgressApiError>);
  });

  it("distinguishes expired authentication from retryable unavailability", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const expiredFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ code: "authentication_required" }, 403));
    const unavailableFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        jsonResponse({ code: "progress_temporarily_unavailable", retryable: true }, 503),
      );

    await expect(
      getLearningProgress("America/Chicago", { fetcher: expiredFetcher }),
    ).rejects.toMatchObject({
      kind: "unauthenticated",
      retryable: false,
    } satisfies Partial<ProgressApiError>);
    await expect(
      getLearningProgress("America/Chicago", { fetcher: unavailableFetcher }),
    ).rejects.toMatchObject({
      kind: "unavailable",
      retryable: true,
    } satisfies Partial<ProgressApiError>);
  });
});
