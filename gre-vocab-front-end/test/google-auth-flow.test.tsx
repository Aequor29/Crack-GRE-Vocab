import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AccountPanel } from "@/components/auth/account-panel";
import { AuthProvider } from "@/components/auth/auth-provider";
import { GoogleSignInControls } from "@/components/auth/google-sign-in-controls";
import {
  AuthApiError,
  cancelGoogleLink,
  confirmGoogleLink,
  getCurrentAccount,
} from "@/lib/api/auth";
import type { GoogleSignInStatus } from "@/lib/auth-page-query";

const navigation = vi.hoisted(() => ({
  refresh: vi.fn(),
  replace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => navigation,
}));

vi.mock("@/lib/api/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/auth")>();
  return {
    ...actual,
    cancelGoogleLink: vi.fn(),
    confirmGoogleLink: vi.fn(),
    getCurrentAccount: vi.fn(),
  };
});

const account = {
  display_name: "Ada Learner",
  email: "learner@example.com",
  id: 7,
};

const cancelGoogleLinkMock = vi.mocked(cancelGoogleLink);
const confirmGoogleLinkMock = vi.mocked(confirmGoogleLink);
const getCurrentAccountMock = vi.mocked(getCurrentAccount);

describe("Google sign-in experience", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    navigation.refresh.mockReset();
    navigation.replace.mockReset();
    cancelGoogleLinkMock.mockReset();
    confirmGoogleLinkMock.mockReset();
    getCurrentAccountMock.mockReset();
    getCurrentAccountMock.mockResolvedValue(null);
  });

  it.each([
    { role: "status", status: "cancelled" },
    { role: "alert", status: "provider-error" },
    { role: "alert", status: "conflict" },
  ] satisfies { role: "alert" | "status"; status: GoogleSignInStatus }[])(
    "shows the accessible $status provider state",
    async ({ role, status }) => {
      render(
        <AuthProvider>
          <GoogleSignInControls status={status} />
        </AuthProvider>,
      );

      expect(await screen.findByRole(role)).not.toBeEmptyDOMElement();
      expect(screen.getByRole("link", { name: "Continue with Google" })).toHaveAttribute(
        "href",
        "http://localhost:8000/api/auth/google/start/",
      );
    },
  );

  it("does not offer a Google action when sign-in is unavailable", async () => {
    render(
      <AuthProvider>
        <GoogleSignInControls status="unavailable" />
      </AuthProvider>,
    );

    expect(await screen.findByRole("button", { name: "Continue with Google" })).toBeDisabled();
    expect(screen.queryByRole("link", { name: "Continue with Google" })).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).not.toBeEmptyDOMElement();

    cleanup();
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");
    render(
      <AuthProvider>
        <GoogleSignInControls />
      </AuthProvider>,
    );

    expect(await screen.findByRole("button", { name: "Continue with Google" })).toBeDisabled();
    expect(screen.getByRole("status")).not.toBeEmptyDOMElement();
  });

  it("confirms a matching password account before linking and signing in", async () => {
    confirmGoogleLinkMock.mockResolvedValue(account);

    render(
      <AuthProvider>
        <GoogleSignInControls status="link-required" />
      </AuthProvider>,
    );

    expect(await screen.findByRole("status")).not.toBeEmptyDOMElement();
    fireEvent.change(screen.getByLabelText("Current password"), {
      target: { value: "durable-recall-river-927" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm Google link" }));

    await waitFor(() =>
      expect(confirmGoogleLinkMock).toHaveBeenCalledWith({
        password: "durable-recall-river-927",
      }),
    );
    expect(navigation.replace).toHaveBeenCalledWith("/account?google=connected");
  });

  it("cancels a pending link without changing the account", async () => {
    cancelGoogleLinkMock.mockResolvedValue();

    render(
      <AuthProvider>
        <GoogleSignInControls status="link-required" />
      </AuthProvider>,
    );

    await screen.findByRole("button", { name: "Cancel linking" });
    fireEvent.click(screen.getByRole("button", { name: "Cancel linking" }));

    expect(await screen.findByRole("status")).not.toBeEmptyDOMElement();
    expect(cancelGoogleLinkMock).toHaveBeenCalledOnce();
  });

  it("associates rejected ownership confirmation with the password field", async () => {
    confirmGoogleLinkMock.mockRejectedValue(
      new AuthApiError("Password proof was rejected.", {
        password: ["Password proof was rejected."],
      }),
    );

    render(
      <AuthProvider>
        <GoogleSignInControls status="link-required" />
      </AuthProvider>,
    );

    const password = await screen.findByLabelText("Current password");
    fireEvent.change(password, { target: { value: "wrong-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm Google link" }));

    expect(await screen.findByText("Password proof was rejected.")).toBeInTheDocument();
    expect(password).toHaveAttribute("aria-invalid", "true");
    expect(password).toHaveAccessibleDescription("Password proof was rejected.");
  });

  it("keeps Google provider conflicts at the form level", async () => {
    confirmGoogleLinkMock.mockRejectedValue(new AuthApiError("Provider conflict."));

    render(
      <AuthProvider>
        <GoogleSignInControls status="link-required" />
      </AuthProvider>,
    );

    const password = await screen.findByLabelText("Current password");
    fireEvent.change(password, { target: { value: "durable-recall-river-927" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm Google link" }));

    expect(await screen.findByRole("alert")).not.toBeEmptyDOMElement();
    expect(password).toHaveAttribute("aria-invalid", "false");
    expect(password).not.toHaveAccessibleDescription();
  });

  it("announces successful Google sign-in on the restored account", async () => {
    getCurrentAccountMock.mockResolvedValue(account);

    render(
      <AuthProvider>
        <AccountPanel googleConnected />
      </AuthProvider>,
    );

    expect(await screen.findByText("Ada Learner")).toBeInTheDocument();
    expect(screen.getByRole("status")).not.toBeEmptyDOMElement();
  });
});
