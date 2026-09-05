import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getLearningInsights,
  getLearningProgress,
  type ProgressApiError,
} from "@/lib/api/progress";
import { learningInsights, learningProgress } from "./progress-builders";

const summary = learningProgress();
const insights = learningInsights();

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

  it("loads validated weekly insights for the requested IANA timezone", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(insights, 200));

    await expect(getLearningInsights("America/Chicago", { fetcher })).resolves.toEqual(insights);
    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:8000/api/progress/insights/?timezone=America%2FChicago",
      expect.objectContaining({ credentials: "include", method: "GET" }),
    );
  });

  it("rejects incomplete weekly insights before the dashboard renders them", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse(
        {
          ...insights,
          learning_curve: insights.learning_curve.slice(0, 11),
        },
        200,
      ),
    );

    await expect(getLearningInsights("America/Chicago", { fetcher })).rejects.toMatchObject({
      kind: "unavailable",
    } satisfies Partial<ProgressApiError>);
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
