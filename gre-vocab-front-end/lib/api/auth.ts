import type {
  ApiMessage,
  AuthValidationError,
  CsrfToken,
  LearnerAccount,
  PasswordResetConfirmRequest,
  PasswordResetStartRequest,
  SignInRequest,
  SignUpRequest,
} from "@/lib/api/generated/schema.generated";
import { configuredApiOrigin } from "@/lib/api/origin";

type OpenApiDocument = typeof import("../../../crackGreVocab/openapi.json");
type OpenApiPaths = OpenApiDocument["paths"];
type IsExact<Actual, Expected> =
  (<Value>() => Value extends Actual ? 1 : 2) extends <Value>() => Value extends Expected ? 1 : 2
    ? true
    : false;

const AUTH_CONTRACT = {
  paths: {
    account: "/api/auth/account/",
    csrf: "/api/auth/csrf/",
    passwordResetConfirm: "/api/auth/password-reset/confirm/",
    passwordResetStart: "/api/auth/password-reset/",
    signIn: "/api/auth/sign-in/",
    signOut: "/api/auth/sign-out/",
    signUp: "/api/auth/sign-up/",
  },
  responseStatusesMatch: {
    account: true,
    csrf: true,
    passwordResetConfirm: true,
    passwordResetStart: true,
    signIn: true,
    signOut: true,
    signUp: true,
  },
} as const satisfies {
  paths: {
    account: keyof OpenApiPaths;
    csrf: keyof OpenApiPaths;
    passwordResetConfirm: keyof OpenApiPaths;
    passwordResetStart: keyof OpenApiPaths;
    signIn: keyof OpenApiPaths;
    signOut: keyof OpenApiPaths;
    signUp: keyof OpenApiPaths;
  };
  responseStatusesMatch: {
    account: IsExact<keyof OpenApiPaths["/api/auth/account/"]["get"]["responses"], "200" | "403">;
    csrf: IsExact<keyof OpenApiPaths["/api/auth/csrf/"]["get"]["responses"], "200">;
    passwordResetConfirm: IsExact<
      keyof OpenApiPaths["/api/auth/password-reset/confirm/"]["post"]["responses"],
      "200" | "400" | "403" | "415"
    >;
    passwordResetStart: IsExact<
      keyof OpenApiPaths["/api/auth/password-reset/"]["post"]["responses"],
      "202" | "400" | "403" | "415"
    >;
    signIn: IsExact<
      keyof OpenApiPaths["/api/auth/sign-in/"]["post"]["responses"],
      "200" | "400" | "401" | "403" | "415"
    >;
    signOut: IsExact<keyof OpenApiPaths["/api/auth/sign-out/"]["post"]["responses"], "204" | "403">;
    signUp: IsExact<
      keyof OpenApiPaths["/api/auth/sign-up/"]["post"]["responses"],
      "201" | "400" | "403" | "415"
    >;
  };
};

export type Account = LearnerAccount;
export type SignInInput = SignInRequest;
export type SignUpInput = SignUpRequest;
export type PasswordResetConfirmInput = PasswordResetConfirmRequest;
export type PasswordResetStartInput = PasswordResetStartRequest;
export type AuthFieldErrors = AuthValidationError;
export type AuthErrorKind =
  | "credentials"
  | "csrf"
  | "recovery"
  | "unauthenticated"
  | "unavailable"
  | "validation";

export class AuthApiError extends Error {
  readonly fieldErrors: AuthFieldErrors;
  readonly kind: AuthErrorKind;

  constructor(kind: AuthErrorKind, message: string, fieldErrors: AuthFieldErrors = {}) {
    super(message);
    this.name = "AuthApiError";
    this.kind = kind;
    this.fieldErrors = fieldErrors;
  }
}

type AuthRequestOptions = {
  fetcher?: typeof fetch;
  signal?: AbortSignal;
};

function apiUrl(path: keyof OpenApiPaths): string {
  const origin = configuredApiOrigin();
  if (!origin) {
    throw new AuthApiError(
      "unavailable",
      "The local API is not configured. Check NEXT_PUBLIC_API_BASE_URL and try again.",
    );
  }
  return `${origin}${path}`;
}

function isAccount(value: unknown): value is Account {
  if (!value || typeof value !== "object") {
    return false;
  }
  const account = value as Partial<Account>;
  return (
    typeof account.id === "number" &&
    typeof account.email === "string" &&
    typeof account.display_name === "string"
  );
}

function isCsrfToken(value: unknown): value is CsrfToken {
  return (
    Boolean(value) &&
    typeof value === "object" &&
    typeof (value as Partial<CsrfToken>).csrf_token === "string"
  );
}

function readFieldErrors(value: unknown): AuthFieldErrors {
  if (!value || typeof value !== "object") {
    return {};
  }

  const source = value as Record<string, unknown>;
  const result: AuthFieldErrors = {};
  for (const field of [
    "email",
    "display_name",
    "password",
    "token",
    "uid",
    "non_field_errors",
  ] as const) {
    const messages = source[field];
    if (Array.isArray(messages) && messages.every((message) => typeof message === "string")) {
      result[field] = messages;
    }
  }
  return result;
}

function isApiMessage(value: unknown): value is ApiMessage {
  return (
    Boolean(value) &&
    typeof value === "object" &&
    typeof (value as Partial<ApiMessage>).detail === "string"
  );
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function isAbortError(error: unknown, signal?: AbortSignal): boolean {
  return signal?.aborted === true || (error instanceof DOMException && error.name === "AbortError");
}

function unavailableError(): AuthApiError {
  return new AuthApiError(
    "unavailable",
    "The local backend is unavailable. Start Django and PostgreSQL, then try again.",
  );
}

async function csrfToken({ fetcher = fetch, signal }: AuthRequestOptions): Promise<string> {
  let response: Response;
  try {
    response = await fetcher(apiUrl(AUTH_CONTRACT.paths.csrf), {
      cache: "no-store",
      credentials: "include",
      headers: { Accept: "application/json" },
      method: "GET",
      signal,
    });
  } catch (error) {
    if (isAbortError(error, signal)) {
      throw error;
    }
    if (error instanceof AuthApiError) {
      throw error;
    }
    throw unavailableError();
  }

  const payload = await readJson(response);
  if (response.status !== 200 || !isCsrfToken(payload)) {
    throw unavailableError();
  }
  return payload.csrf_token;
}

async function postJsonWithCsrf(
  path: keyof OpenApiPaths,
  input: unknown,
  { fetcher = fetch, signal }: AuthRequestOptions,
): Promise<{ payload: unknown; response: Response }> {
  const token = await csrfToken({ fetcher, signal });
  let response: Response;
  try {
    response = await fetcher(apiUrl(path), {
      body: JSON.stringify(input),
      cache: "no-store",
      credentials: "include",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRFToken": token,
      },
      method: "POST",
      signal,
    });
  } catch (error) {
    if (isAbortError(error, signal)) {
      throw error;
    }
    if (error instanceof AuthApiError) {
      throw error;
    }
    throw unavailableError();
  }

  return { payload: await readJson(response), response };
}

async function mutateAccount(
  path: typeof AUTH_CONTRACT.paths.signIn | typeof AUTH_CONTRACT.paths.signUp,
  input: SignInInput | SignUpInput,
  expectedStatus: 200 | 201,
  { fetcher = fetch, signal }: AuthRequestOptions,
): Promise<Account> {
  const { payload, response } = await postJsonWithCsrf(path, input, { fetcher, signal });
  if (response.status === expectedStatus && isAccount(payload)) {
    return payload;
  }
  if (response.status === 400) {
    throw new AuthApiError(
      "validation",
      "Check the highlighted fields and try again.",
      readFieldErrors(payload),
    );
  }
  if (response.status === 401) {
    throw new AuthApiError("credentials", "Email or password is incorrect.");
  }
  if (response.status === 403) {
    throw new AuthApiError("csrf", "Your form expired. Please try again.");
  }
  if (response.status === 415) {
    throw new AuthApiError("unavailable", "The account request format was rejected.");
  }
  throw unavailableError();
}

async function submitPasswordRecoveryRequest(
  path:
    | typeof AUTH_CONTRACT.paths.passwordResetStart
    | typeof AUTH_CONTRACT.paths.passwordResetConfirm,
  input: PasswordResetStartInput | PasswordResetConfirmInput,
  expectedStatus: 200 | 202,
  { fetcher = fetch, signal }: AuthRequestOptions,
): Promise<string> {
  const { payload, response } = await postJsonWithCsrf(path, input, { fetcher, signal });
  if (response.status === expectedStatus && isApiMessage(payload)) {
    return payload.detail;
  }
  if (response.status === 400) {
    if (isApiMessage(payload)) {
      throw new AuthApiError("recovery", payload.detail);
    }
    throw new AuthApiError(
      "validation",
      "Check the highlighted fields and try again.",
      readFieldErrors(payload),
    );
  }
  if (response.status === 403) {
    throw new AuthApiError("csrf", "Your form expired. Please try again.");
  }
  if (response.status === 415) {
    throw new AuthApiError("unavailable", "The recovery request format was rejected.");
  }
  throw unavailableError();
}

export async function getCurrentAccount({
  fetcher = fetch,
  signal,
}: AuthRequestOptions = {}): Promise<Account | null> {
  let response: Response;
  try {
    response = await fetcher(apiUrl(AUTH_CONTRACT.paths.account), {
      cache: "no-store",
      credentials: "include",
      headers: { Accept: "application/json" },
      method: "GET",
      signal,
    });
  } catch (error) {
    if (isAbortError(error, signal)) {
      throw error;
    }
    if (error instanceof AuthApiError) {
      throw error;
    }
    throw unavailableError();
  }

  const payload = await readJson(response);
  if (response.status === 200 && isAccount(payload)) {
    return payload;
  }
  if (response.status === 403) {
    return null;
  }
  throw unavailableError();
}

export function signUp(input: SignUpInput, options: AuthRequestOptions = {}): Promise<Account> {
  return mutateAccount(AUTH_CONTRACT.paths.signUp, input, 201, options);
}

export function signIn(input: SignInInput, options: AuthRequestOptions = {}): Promise<Account> {
  return mutateAccount(AUTH_CONTRACT.paths.signIn, input, 200, options);
}

export function requestPasswordReset(
  input: PasswordResetStartInput,
  options: AuthRequestOptions = {},
): Promise<string> {
  return submitPasswordRecoveryRequest(AUTH_CONTRACT.paths.passwordResetStart, input, 202, options);
}

export function confirmPasswordReset(
  input: PasswordResetConfirmInput,
  options: AuthRequestOptions = {},
): Promise<string> {
  return submitPasswordRecoveryRequest(
    AUTH_CONTRACT.paths.passwordResetConfirm,
    input,
    200,
    options,
  );
}

export async function signOut({ fetcher = fetch, signal }: AuthRequestOptions = {}): Promise<void> {
  const token = await csrfToken({ fetcher, signal });
  let response: Response;
  try {
    response = await fetcher(apiUrl(AUTH_CONTRACT.paths.signOut), {
      cache: "no-store",
      credentials: "include",
      headers: {
        Accept: "application/json",
        "X-CSRFToken": token,
      },
      method: "POST",
      signal,
    });
  } catch (error) {
    if (isAbortError(error, signal)) {
      throw error;
    }
    if (error instanceof AuthApiError) {
      throw error;
    }
    throw unavailableError();
  }

  if (response.status === 204) {
    return;
  }
  if (response.status === 403) {
    throw new AuthApiError("csrf", "Your form expired. Please try again.");
  }
  throw unavailableError();
}
