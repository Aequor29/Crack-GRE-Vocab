import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AccountPanel } from "@/components/auth/account-panel";
import { AuthProvider } from "@/components/auth/auth-provider";
import {
  GoogleSignInControls,
  type GoogleSignInStatus,
} from "@/components/auth/google-sign-in-controls";
import {
  AuthApiError,
  cancelGoogleLink,
  confirmGoogleLink,
  getCurrentAccount,
} from "@/lib/api/auth";

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
    ["cancelled", "Google sign-in was cancelled. No account changes were made."],
    ["provider-error", "Google sign-in could not be completed. Please try again."],
    ["conflict", "This Google identity is already connected to a different account."],
    ["unavailable", "Google sign-in is not configured for this environment."],
  ] satisfies [GoogleSignInStatus, string][])(
    "shows the accessible %s provider state",
    async (status, message) => {
      render(
        <AuthProvider>
          <GoogleSignInControls status={status} />
        </AuthProvider>,
      );

      expect(await screen.findByText(message)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Continue with Google" })).toHaveAttribute(
        "href",
        "http://localhost:8000/api/auth/google/start/",
      );
    },
  );

  it("confirms a matching password account before linking and signing in", async () => {
    confirmGoogleLinkMock.mockResolvedValue(account);

    render(
      <AuthProvider>
        <GoogleSignInControls status="link-required" />
      </AuthProvider>,
    );

    expect(
      await screen.findByText("Confirm this is your existing account before linking Google."),
    ).toHaveAttribute("role", "status");
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

    expect(
      await screen.findByText("Google linking was cancelled. No account changes were made."),
    ).toHaveAttribute("role", "status");
    expect(cancelGoogleLinkMock).toHaveBeenCalledOnce();
  });

  it("associates rejected ownership confirmation with the password field", async () => {
    confirmGoogleLinkMock.mockRejectedValue(
      new AuthApiError("credentials", "Enter the current password for this account."),
    );

    render(
      <AuthProvider>
        <GoogleSignInControls status="link-required" />
      </AuthProvider>,
    );

    const password = await screen.findByLabelText("Current password");
    fireEvent.change(password, { target: { value: "wrong-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm Google link" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter the current password for this account.",
    );
    expect(password).toHaveAttribute("aria-invalid", "true");
    expect(password).toHaveAccessibleDescription("Enter the current password for this account.");
  });

  it("announces successful Google sign-in on the restored account", async () => {
    getCurrentAccountMock.mockResolvedValue(account);

    render(
      <AuthProvider>
        <AccountPanel googleConnected />
      </AuthProvider>,
    );

    expect(await screen.findByText("Google sign-in is connected to this account.")).toHaveAttribute(
      "role",
      "status",
    );
    expect(screen.getByText("Ada Learner")).toBeInTheDocument();
  });
});
