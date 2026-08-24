import { afterEach, describe, expect, it, vi } from "vitest";

import {
  cancelGoogleLink,
  confirmGoogleLink,
  confirmPasswordReset,
  getCurrentAccount,
  googleSignInUrl,
  requestPasswordReset,
  signIn,
  signOut,
  signUp,
} from "@/lib/api/auth";

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

    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/auth/csrf/",
      expect.objectContaining({ credentials: "include", method: "GET" }),
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/auth/sign-up/",
      expect.objectContaining({
        body: JSON.stringify({
          display_name: "Ada Learner",
          email: "learner@example.com",
          password: "durable-recall-river-927",
        }),
        credentials: "include",
        headers: expect.objectContaining({ "X-CSRFToken": "masked-token" }),
        method: "POST",
      }),
    );
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
    const offlineFetcher = vi.fn<typeof fetch>().mockRejectedValue(new TypeError("offline"));

    await expect(getCurrentAccount({ fetcher: anonymousFetcher })).resolves.toBeNull();
    await expect(getCurrentAccount({ fetcher: malformedFetcher })).rejects.toMatchObject({
      kind: "unavailable",
    });
    await expect(getCurrentAccount({ fetcher: offlineFetcher })).rejects.toMatchObject({
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

  it("requests password recovery with fresh CSRF protection", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "recovery-token" }, 200))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            detail: "If an account can be recovered, a password reset link has been sent.",
          },
          202,
        ),
      );

    await expect(requestPasswordReset({ email: "learner@example.com" }, { fetcher })).resolves.toBe(
      "If an account can be recovered, a password reset link has been sent.",
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/auth/password-reset/",
      expect.objectContaining({
        body: JSON.stringify({ email: "learner@example.com" }),
        credentials: "include",
        headers: expect.objectContaining({ "X-CSRFToken": "recovery-token" }),
        method: "POST",
      }),
    );
  });

  it("builds the provider start URL from the configured API origin", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");

    expect(googleSignInUrl()).toBe("http://localhost:8000/api/auth/google/start/");
  });

  it("confirms and cancels a pending Google link with fresh CSRF tokens", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const confirmationFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "confirm-token" }, 200))
      .mockResolvedValueOnce(jsonResponse(account, 200));
    const cancellationFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "cancel-token" }, 200))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(
      confirmGoogleLink({ password: "durable-recall-river-927" }, { fetcher: confirmationFetcher }),
    ).resolves.toEqual(account);
    await expect(cancelGoogleLink({ fetcher: cancellationFetcher })).resolves.toBeUndefined();

    expect(confirmationFetcher).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/auth/google/link/confirm/",
      expect.objectContaining({
        body: JSON.stringify({ password: "durable-recall-river-927" }),
        credentials: "include",
        method: "POST",
      }),
    );
    expect(cancellationFetcher).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/auth/google/link/cancel/",
      expect.objectContaining({
        credentials: "include",
        method: "POST",
      }),
    );
  });

  it("confirms recovery and distinguishes invalid links from weak passwords", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const input = {
      password: "focused-review-summit-482",
      token: "opaque-token",
      uid: "opaque-uid",
    };
    const acceptedFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "confirm-token" }, 200))
      .mockResolvedValueOnce(
        jsonResponse({ detail: "Password reset complete. Sign in with your new password." }, 200),
      );
    const invalidFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "invalid-token" }, 200))
      .mockResolvedValueOnce(
        jsonResponse({ detail: "This password reset link is invalid or has expired." }, 400),
      );
    const weakPasswordFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "weak-token" }, 200))
      .mockResolvedValueOnce(jsonResponse({ password: ["This password is too common."] }, 400));

    await expect(confirmPasswordReset(input, { fetcher: acceptedFetcher })).resolves.toBe(
      "Password reset complete. Sign in with your new password.",
    );
    expect(acceptedFetcher).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/auth/password-reset/confirm/",
      expect.objectContaining({ body: JSON.stringify(input), method: "POST" }),
    );
    await expect(confirmPasswordReset(input, { fetcher: invalidFetcher })).rejects.toMatchObject({
      kind: "recovery",
      message: "This password reset link is invalid or has expired.",
    });
    await expect(
      confirmPasswordReset(input, { fetcher: weakPasswordFetcher }),
    ).rejects.toMatchObject({
      fieldErrors: { password: ["This password is too common."] },
      kind: "validation",
    });
  });

  it("keeps Google link authentication and identity conflicts explicit", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const wrongPasswordFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "first-token" }, 200))
      .mockResolvedValueOnce(
        jsonResponse({ detail: "Enter the current password for this account." }, 401),
      );
    const conflictFetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "second-token" }, 200))
      .mockResolvedValueOnce(
        jsonResponse({ detail: "This Google identity cannot be linked to that account." }, 409),
      );

    await expect(
      confirmGoogleLink({ password: "wrong" }, { fetcher: wrongPasswordFetcher }),
    ).rejects.toMatchObject({
      kind: "credentials",
      message: "Enter the current password for this account.",
    });
    await expect(
      confirmGoogleLink({ password: "durable-recall-river-927" }, { fetcher: conflictFetcher }),
    ).rejects.toMatchObject({
      kind: "conflict",
      message: "This Google identity cannot be linked to that account.",
    });
  });
});
