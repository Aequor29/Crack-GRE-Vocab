import { afterEach, describe, expect, it, vi } from "vitest";

import { checkReadiness } from "@/lib/api/readiness";

const jsonResponse = (body: unknown, status: number) =>
  new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });

describe("readiness client", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("maps the generated ready response and sends a private browser request", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://127.0.0.1:8000");
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ status: "ready", database: "available" }, 200));

    await expect(checkReadiness({ fetcher })).resolves.toBe("ready");
    expect(fetcher).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/readiness/",
      expect.objectContaining({
        cache: "no-store",
        credentials: "omit",
        method: "GET",
      }),
    );
  });

  it("distinguishes a typed database outage from an unreachable backend", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const databaseUnavailable = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ status: "unavailable", database: "unavailable" }, 503));
    const backendUnavailable = vi.fn<typeof fetch>().mockRejectedValue(new TypeError("offline"));

    await expect(checkReadiness({ fetcher: databaseUnavailable })).resolves.toBe(
      "database-unavailable",
    );
    await expect(checkReadiness({ fetcher: backendUnavailable })).resolves.toBe(
      "backend-unavailable",
    );
  });

  it("treats missing configuration and malformed responses as backend unavailable", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ status: "ready", database: "unknown" }, 200));

    await expect(checkReadiness({ fetcher })).resolves.toBe("backend-unavailable");
    expect(fetcher).not.toHaveBeenCalled();

    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    await expect(checkReadiness({ fetcher })).resolves.toBe("backend-unavailable");
  });
});
