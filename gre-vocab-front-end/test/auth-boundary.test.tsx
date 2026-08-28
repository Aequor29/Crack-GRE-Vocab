import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AccountForm } from "@/components/auth/account-form";
import { AuthProvider } from "@/components/auth/auth-provider";

const navigation = vi.hoisted(() => ({
  refresh: vi.fn(),
  replace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => navigation,
}));

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

describe("rendered authentication boundary", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    navigation.refresh.mockReset();
    navigation.replace.mockReset();
  });

  it("signs in through AuthProvider and the real credentialed client", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(null, { status: 403 }))
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "masked-token" }, 200))
      .mockResolvedValueOnce(jsonResponse(account, 200));
    vi.stubGlobal("fetch", fetcher);

    render(
      <AuthProvider>
        <AccountForm mode="sign-in" />
      </AuthProvider>,
    );

    const submit = await screen.findByRole("button", { name: "Sign in" });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "learner@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "durable-recall-river-927" },
    });
    fireEvent.click(submit);

    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/dashboard"));
    expect(screen.getByText("You are already signed in.")).toBeInTheDocument();
    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/auth/account/",
      expect.objectContaining({ credentials: "include", method: "GET" }),
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/auth/csrf/",
      expect.objectContaining({ credentials: "include", method: "GET" }),
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/api/auth/sign-in/",
      expect.objectContaining({
        body: JSON.stringify({
          email: "learner@example.com",
          password: "durable-recall-river-927",
        }),
        credentials: "include",
        headers: expect.objectContaining({ "X-CSRFToken": "masked-token" }),
        method: "POST",
      }),
    );
  });
});
