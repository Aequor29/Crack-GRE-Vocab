import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  PasswordResetConfirmationForm,
  PasswordResetRequestForm,
} from "@/components/auth/password-recovery-form";
import { AuthApiError, confirmPasswordReset, requestPasswordReset } from "@/lib/api/auth";

vi.mock("@/lib/api/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/auth")>();
  return {
    ...actual,
    confirmPasswordReset: vi.fn(),
    requestPasswordReset: vi.fn(),
  };
});

const confirmPasswordResetMock = vi.mocked(confirmPasswordReset);
const requestPasswordResetMock = vi.mocked(requestPasswordReset);

describe("password recovery experience", () => {
  afterEach(cleanup);

  beforeEach(() => {
    confirmPasswordResetMock.mockReset();
    requestPasswordResetMock.mockReset();
  });

  it("requests recovery and announces the generic delivery result", async () => {
    let finishRequest: ((message: string) => void) | undefined;
    requestPasswordResetMock.mockReturnValue(
      new Promise((resolve) => {
        finishRequest = resolve;
      }),
    );

    render(<PasswordResetRequestForm />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "learner@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(screen.getByRole("button", { name: "Sending…" })).toBeDisabled();
    expect(requestPasswordResetMock).toHaveBeenCalledWith({
      email: "learner@example.com",
    });

    finishRequest?.("If an account can be recovered, a password reset link has been sent.");
    expect(await screen.findByRole("status")).toHaveTextContent("If an account can be recovered");
    expect(screen.getByRole("link", { name: "Return to sign in" })).toHaveAttribute(
      "href",
      "/sign-in",
    );
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Sending…" })).not.toBeInTheDocument(),
    );
  });

  it("rejects incomplete links without calling the API", () => {
    render(<PasswordResetConfirmationForm token={null} uid={null} />);

    expect(screen.getByRole("alert")).toHaveTextContent("invalid or has expired");
    expect(screen.getByRole("link", { name: "Request a new reset link" })).toHaveAttribute(
      "href",
      "/forgot-password",
    );
    expect(confirmPasswordResetMock).not.toHaveBeenCalled();
  });

  it("sets a new password and directs the learner back to sign in", async () => {
    confirmPasswordResetMock.mockResolvedValue(
      "Password reset complete. Sign in with your new password.",
    );
    render(<PasswordResetConfirmationForm token="opaque-token" uid="opaque-uid" />);

    fireEvent.change(screen.getByLabelText("New password"), {
      target: { value: "focused-review-summit-482" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Reset password" }));

    await waitFor(() =>
      expect(confirmPasswordResetMock).toHaveBeenCalledWith({
        password: "focused-review-summit-482",
        token: "opaque-token",
        uid: "opaque-uid",
      }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent("Password reset complete");
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/sign-in");
  });

  it("announces an expired or reused confirmation link", async () => {
    confirmPasswordResetMock.mockRejectedValue(
      new AuthApiError("recovery", "This password reset link is invalid or has expired."),
    );
    render(<PasswordResetConfirmationForm token="expired-token" uid="opaque-uid" />);

    fireEvent.change(screen.getByLabelText("New password"), {
      target: { value: "focused-review-summit-482" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Reset password" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("invalid or has expired");
  });
});
