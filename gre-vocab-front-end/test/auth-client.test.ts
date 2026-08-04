import { afterEach, describe, expect, it, vi } from "vitest";

import { getCurrentAccount, signIn, signOut, signUp } from "@/lib/api/auth";

const account = {
  display_name: "Ada Learner",
  email: "learner@example.com",
  id: 7,
};

const jsonResponse = (body: unknown, status: number) =>
  new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });

describe("account API client", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("creates an account with a fresh CSRF token and credentialed JSON request", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "masked-token" }, 200))
      .mockResolvedValueOnce(jsonResponse(account, 201));

    await expect(
      signUp(
        {
          display_name: "Ada Learner",
          email: "learner@example.com",
          password: "durable-recall-river-927",
        },
        { fetcher },
      ),
    ).resolves.toEqual(account);

    expect(fetcher).toHaveBeenNthCalledWith(1, "http://localhost:8000/api/auth/csrf/", {
      cache: "no-store",
      credentials: "include",
      headers: { Accept: "application/json" },
      method: "GET",
      signal: undefined,
    });
    expect(fetcher).toHaveBeenNthCalledWith(2, "http://localhost:8000/api/auth/sign-up/", {
      body: JSON.stringify({
        display_name: "Ada Learner",
        email: "learner@example.com",
        password: "durable-recall-river-927",
      }),
      cache: "no-store",
      credentials: "include",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRFToken": "masked-token",
      },
      method: "POST",
      signal: undefined,
    });
  });

  it("preserves typed validation errors and maps bad credentials generically", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const validationFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "first-token" }, 200))
      .mockResolvedValueOnce(
        jsonResponse({ email: ["An account with this email already exists."] }, 400),
      );
    const credentialsFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "second-token" }, 200))
      .mockResolvedValueOnce(jsonResponse({ detail: "Email or password is incorrect." }, 401));

    await expect(
      signUp(
        {
          display_name: "Ada Learner",
          email: "learner@example.com",
          password: "durable-recall-river-927",
        },
        { fetcher: validationFetcher },
      ),
    ).rejects.toMatchObject({
      fieldErrors: { email: ["An account with this email already exists."] },
      kind: "validation",
    });
    await expect(
      signIn({ email: "learner@example.com", password: "wrong" }, { fetcher: credentialsFetcher }),
    ).rejects.toMatchObject({
      fieldErrors: {},
      kind: "credentials",
      message: "Email or password is incorrect.",
    });
  });

  it("distinguishes an absent session from an invalid backend response", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const anonymousFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(null, { status: 403 }));
    const malformedFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ email: "missing-account-fields@example.com" }, 200));

    await expect(getCurrentAccount({ fetcher: anonymousFetcher })).resolves.toBeNull();
    await expect(getCurrentAccount({ fetcher: malformedFetcher })).rejects.toMatchObject({
      kind: "unavailable",
    });
  });

  it("ends a session only after fetching a fresh CSRF token", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "signout-token" }, 200))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(signOut({ fetcher })).resolves.toBeUndefined();
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/auth/sign-out/",
      expect.objectContaining({
        credentials: "include",
        headers: {
          Accept: "application/json",
          "X-CSRFToken": "signout-token",
        },
        method: "POST",
      }),
    );
  });
});
