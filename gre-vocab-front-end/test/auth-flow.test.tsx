import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AccountForm } from "@/components/auth/account-form";
import { AccountPanel } from "@/components/auth/account-panel";
import { AuthProvider, useAuth } from "@/components/auth/auth-provider";
import { AuthApiError, getCurrentAccount, signIn, signOut, signUp } from "@/lib/api/auth";

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
    getCurrentAccount: vi.fn(),
    signIn: vi.fn(),
    signOut: vi.fn(),
    signUp: vi.fn(),
  };
});

const account = {
  display_name: "Ada Learner",
  email: "learner@example.com",
  id: 7,
};

const getCurrentAccountMock = vi.mocked(getCurrentAccount);
const signInMock = vi.mocked(signIn);
const signOutMock = vi.mocked(signOut);
const signUpMock = vi.mocked(signUp);

function RefreshHarness() {
  const auth = useAuth();
  return (
    <div>
      <p>{auth.account?.display_name ?? auth.status}</p>
      <button onClick={() => void auth.refresh()} type="button">
        Refresh session
      </button>
    </div>
  );
}

describe("learner account experience", () => {
  afterEach(cleanup);

  beforeEach(() => {
    navigation.refresh.mockReset();
    navigation.replace.mockReset();
    getCurrentAccountMock.mockReset();
    signInMock.mockReset();
    signOutMock.mockReset();
    signUpMock.mockReset();
  });

  it("restores an authenticated account and signs out with a pending state", async () => {
    let finishSignOut: (() => void) | undefined;
    getCurrentAccountMock.mockResolvedValue(account);
    signOutMock.mockReturnValue(
      new Promise((resolve) => {
        finishSignOut = resolve;
      }),
    );

    render(
      <AuthProvider>
        <AccountPanel />
      </AuthProvider>,
    );

    expect(await screen.findByText("Ada Learner")).toBeInTheDocument();
    expect(screen.getByText("learner@example.com")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(screen.getByRole("button", { name: "Signing out…" })).toBeDisabled();

    finishSignOut?.();
    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/sign-in"));
  });

  it("protects the account screen when session restoration is anonymous", async () => {
    getCurrentAccountMock.mockResolvedValue(null);

    render(
      <AuthProvider>
        <AccountPanel />
      </AuthProvider>,
    );

    expect(await screen.findByRole("status")).not.toBeEmptyDOMElement();
    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/sign-in"));
    expect(screen.getByRole("link", { name: "Continue to sign in" })).toHaveAttribute(
      "href",
      "/sign-in",
    );
  });

  it("recovers session restoration after a temporary backend failure", async () => {
    getCurrentAccountMock
      .mockRejectedValueOnce(new TypeError("offline"))
      .mockResolvedValueOnce(account);

    render(
      <AuthProvider>
        <AccountPanel />
      </AuthProvider>,
    );

    expect(await screen.findByRole("alert")).not.toBeEmptyDOMElement();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Ada Learner")).toBeInTheDocument();
  });

  it("lets the latest session refresh own the rendered state", async () => {
    let finishFirstRequest: ((restored: typeof account) => void) | undefined;
    let finishSecondRequest: ((restored: null) => void) | undefined;
    getCurrentAccountMock
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finishFirstRequest = resolve;
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finishSecondRequest = resolve;
          }),
      );

    render(
      <AuthProvider>
        <RefreshHarness />
      </AuthProvider>,
    );

    await waitFor(() => expect(getCurrentAccountMock).toHaveBeenCalledOnce());
    fireEvent.click(screen.getByRole("button", { name: "Refresh session" }));

    await waitFor(() => expect(getCurrentAccountMock).toHaveBeenCalledTimes(2));
    finishSecondRequest?.(null);
    expect(await screen.findByText("unauthenticated")).toBeInTheDocument();

    finishFirstRequest?.(account);
    await waitFor(() => expect(screen.queryByText("Ada Learner")).not.toBeInTheDocument());
  });

  it("submits an accessible signup and routes to the dashboard", async () => {
    getCurrentAccountMock.mockResolvedValue(null);
    signUpMock.mockResolvedValue(account);

    render(
      <AuthProvider>
        <AccountForm mode="sign-up" />
      </AuthProvider>,
    );

    const submit = await screen.findByRole("button", { name: "Create account" });
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Ada Learner" } });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "learner@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "durable-recall-river-927" },
    });
    fireEvent.click(submit);

    await waitFor(() =>
      expect(signUpMock).toHaveBeenCalledWith({
        display_name: "Ada Learner",
        email: "learner@example.com",
        password: "durable-recall-river-927",
      }),
    );
    expect(navigation.replace).toHaveBeenCalledWith("/dashboard");
  });

  it("associates server validation errors with the signup field", async () => {
    getCurrentAccountMock.mockResolvedValue(null);
    signUpMock.mockRejectedValue(
      new AuthApiError("Account creation was rejected.", {
        email: ["An account with this email already exists."],
      }),
    );

    render(
      <AuthProvider>
        <AccountForm mode="sign-up" />
      </AuthProvider>,
    );

    await screen.findByRole("button", { name: "Create account" });
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Ada Learner" } });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "learner@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "durable-recall-river-927" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).not.toBeEmptyDOMElement();
    const email = screen.getByLabelText("Email");
    expect(email).toHaveAttribute("aria-invalid", "true");
    expect(email).toHaveAccessibleDescription("An account with this email already exists.");
  });
});
