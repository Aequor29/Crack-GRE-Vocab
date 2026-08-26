"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  type Account,
  type GoogleLinkConfirmInput,
  getCurrentAccount,
  cancelGoogleLink as requestCancelGoogleLink,
  confirmGoogleLink as requestConfirmGoogleLink,
  signIn as requestSignIn,
  signOut as requestSignOut,
  signUp as requestSignUp,
  type SignInInput,
  type SignUpInput,
} from "@/lib/api/auth";

export type AuthStatus = "authenticated" | "checking" | "unauthenticated" | "unavailable";

type AuthContextValue = {
  account: Account | null;
  cancelGoogleLink: () => Promise<void>;
  confirmGoogleLink: (input: GoogleLinkConfirmInput) => Promise<Account>;
  refresh: () => Promise<void>;
  signIn: (input: SignInInput) => Promise<Account>;
  signOut: () => Promise<void>;
  signUp: (input: SignUpInput) => Promise<Account>;
  status: AuthStatus;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<Account | null>(null);
  const [status, setStatus] = useState<AuthStatus>("checking");
  const activeRequest = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setStatus("checking");

    try {
      const restoredAccount = await getCurrentAccount({ signal: controller.signal });
      if (!controller.signal.aborted) {
        setAccount(restoredAccount);
        setStatus(restoredAccount ? "authenticated" : "unauthenticated");
      }
    } catch {
      if (!controller.signal.aborted) {
        setAccount(null);
        setStatus("unavailable");
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
    return () => activeRequest.current?.abort();
  }, [refresh]);

  const signIn = useCallback(async (input: SignInInput) => {
    const authenticatedAccount = await requestSignIn(input);
    setAccount(authenticatedAccount);
    setStatus("authenticated");
    return authenticatedAccount;
  }, []);

  const signUp = useCallback(async (input: SignUpInput) => {
    const authenticatedAccount = await requestSignUp(input);
    setAccount(authenticatedAccount);
    setStatus("authenticated");
    return authenticatedAccount;
  }, []);

  const signOut = useCallback(async () => {
    await requestSignOut();
    setAccount(null);
    setStatus("unauthenticated");
  }, []);

  const confirmGoogleLink = useCallback(async (input: GoogleLinkConfirmInput) => {
    const authenticatedAccount = await requestConfirmGoogleLink(input);
    setAccount(authenticatedAccount);
    setStatus("authenticated");
    return authenticatedAccount;
  }, []);

  const cancelGoogleLink = useCallback(async () => {
    await requestCancelGoogleLink();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      account,
      cancelGoogleLink,
      confirmGoogleLink,
      refresh,
      signIn,
      signOut,
      signUp,
      status,
    }),
    [account, cancelGoogleLink, confirmGoogleLink, refresh, signIn, signOut, signUp, status],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider.");
  }
  return context;
}
