import { afterEach, describe, expect, it, vi } from "vitest";

import { type ApiTransportError, getApiJson, postApiJsonWithCsrf } from "@/lib/api/transport";

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });

describe("API transport", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("resolves the configured origin and sends private no-store JSON GET requests", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ ready: true }));

    await expect(getApiJson("/api/example/", { fetcher })).resolves.toMatchObject({
      payload: { ready: true },
    });
    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:8000/api/example/",
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
        headers: { Accept: "application/json" },
        method: "GET",
      }),
    );
  });

  it("obtains a fresh credentialed CSRF token before a JSON mutation", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "masked-token" }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(
      postApiJsonWithCsrf("/api/auth/csrf/", "/api/example/", { answer: true }, { fetcher }),
    ).resolves.toMatchObject({ payload: null });

    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/auth/csrf/",
      expect.objectContaining({ credentials: "include", method: "GET" }),
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/example/",
      expect.objectContaining({
        body: JSON.stringify({ answer: true }),
        credentials: "include",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": "masked-token",
        },
        method: "POST",
      }),
    );
  });

  it("preserves aborts and returns typed configuration, network, and CSRF failures", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const controller = new AbortController();
    const abort = new DOMException("aborted", "AbortError");
    controller.abort();
    const abortedFetcher = vi.fn<typeof fetch>().mockRejectedValue(abort);
    const offlineFetcher = vi.fn<typeof fetch>().mockRejectedValue(new TypeError("offline"));
    const invalidCsrfFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ csrf_token: 42 }));

    await expect(
      getApiJson("/api/example/", {
        fetcher: abortedFetcher,
        signal: controller.signal,
      }),
    ).rejects.toBe(abort);
    expect(abortedFetcher).toHaveBeenCalledWith(
      "http://localhost:8000/api/example/",
      expect.objectContaining({ signal: controller.signal }),
    );
    await expect(getApiJson("/api/example/", { fetcher: offlineFetcher })).rejects.toMatchObject({
      kind: "network",
    } satisfies Partial<ApiTransportError>);
    await expect(
      postApiJsonWithCsrf("/api/auth/csrf/", "/api/example/", undefined, {
        fetcher: invalidCsrfFetcher,
      }),
    ).rejects.toMatchObject({ kind: "csrf-token" } satisfies Partial<ApiTransportError>);

    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");
    const unconfiguredFetcher = vi.fn<typeof fetch>();
    await expect(
      getApiJson("/api/example/", { fetcher: unconfiguredFetcher }),
    ).rejects.toMatchObject({ kind: "configuration" } satisfies Partial<ApiTransportError>);
    expect(unconfiguredFetcher).not.toHaveBeenCalled();
  });
});
