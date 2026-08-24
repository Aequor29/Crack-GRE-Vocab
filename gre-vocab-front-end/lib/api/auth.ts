import type {
  ApiMessage,
  AuthValidationError,
  GoogleLinkConfirmRequest,
  LearnerAccount,
  PasswordResetConfirmRequest,
  PasswordResetStartRequest,
  SignInRequest,
  SignUpRequest,
} from "@/lib/api/generated/schema.generated";
import {
  type ApiJsonResult,
  type ApiRequestOptions,
  ApiTransportError,
  buildApiUrl,
  getApiJson,
  postApiJsonWithCsrf,
} from "@/lib/api/transport";

type OpenApiDocument = typeof import("../../../crackGreVocab/openapi.json");
type OpenApiPaths = OpenApiDocument["paths"];
const AUTH_PATHS = {
  account: "/api/auth/account/",
  csrf: "/api/auth/csrf/",
  passwordResetConfirm: "/api/auth/password-reset/confirm/",
  passwordResetStart: "/api/auth/password-reset/",
  googleLinkCancel: "/api/auth/google/link/cancel/",
  googleLinkConfirm: "/api/auth/google/link/confirm/",
  signIn: "/api/auth/sign-in/",
  signOut: "/api/auth/sign-out/",
  signUp: "/api/auth/sign-up/",
} as const satisfies Record<string, keyof OpenApiPaths>;
const GOOGLE_START_PATH = "/api/auth/google/start/";

export type Account = LearnerAccount;
export type GoogleLinkConfirmInput = GoogleLinkConfirmRequest;
export type SignInInput = SignInRequest;
export type SignUpInput = SignUpRequest;
export type PasswordResetConfirmInput = PasswordResetConfirmRequest;
export type PasswordResetStartInput = PasswordResetStartRequest;
export type AuthFieldErrors = AuthValidationError;
export type AuthErrorKind =
  | "conflict"
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

type AuthRequestOptions = ApiRequestOptions;

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

function readApiMessage(value: unknown): string | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const detail = (value as { detail?: unknown }).detail;
  return typeof detail === "string" ? detail : null;
}

function unavailableError(): AuthApiError {
  return new AuthApiError(
    "unavailable",
    "The local backend is unavailable. Start Django and PostgreSQL, then try again.",
  );
}

function throwAuthTransportError(error: unknown): never {
  if (error instanceof ApiTransportError) {
    if (error.kind === "configuration") {
      throw new AuthApiError(
        "unavailable",
        "The local API is not configured. Check NEXT_PUBLIC_API_BASE_URL and try again.",
      );
    }
    throw unavailableError();
  }
  throw error;
}

async function getAuthJson(
  path: keyof OpenApiPaths,
  options: AuthRequestOptions,
): Promise<ApiJsonResult> {
  try {
    return await getApiJson(path, options);
  } catch (error) {
    throwAuthTransportError(error);
  }
}

async function postAuthJsonWithCsrf(
  path: keyof OpenApiPaths,
  input: unknown | undefined,
  options: AuthRequestOptions,
): Promise<ApiJsonResult> {
  try {
    return await postApiJsonWithCsrf(AUTH_PATHS.csrf, path, input, options);
  } catch (error) {
    throwAuthTransportError(error);
  }
}

async function mutateAccount(
  path: typeof AUTH_PATHS.signIn | typeof AUTH_PATHS.signUp,
  input: SignInInput | SignUpInput,
  expectedStatus: 200 | 201,
  options: AuthRequestOptions,
): Promise<Account> {
  const { payload, response } = await postAuthJsonWithCsrf(path, input, options);
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
  path: typeof AUTH_PATHS.passwordResetStart | typeof AUTH_PATHS.passwordResetConfirm,
  input: PasswordResetStartInput | PasswordResetConfirmInput,
  expectedStatus: 200 | 202,
  options: AuthRequestOptions,
): Promise<string> {
  const { payload, response } = await postAuthJsonWithCsrf(path, input, options);
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

export async function getCurrentAccount(options: AuthRequestOptions = {}): Promise<Account | null> {
  const { payload, response } = await getAuthJson(AUTH_PATHS.account, options);
  if (response.status === 200 && isAccount(payload)) {
    return payload;
  }
  if (response.status === 403) {
    return null;
  }
  throw unavailableError();
}

export function signUp(input: SignUpInput, options: AuthRequestOptions = {}): Promise<Account> {
  return mutateAccount(AUTH_PATHS.signUp, input, 201, options);
}

export function signIn(input: SignInInput, options: AuthRequestOptions = {}): Promise<Account> {
  return mutateAccount(AUTH_PATHS.signIn, input, 200, options);
}

export function requestPasswordReset(
  input: PasswordResetStartInput,
  options: AuthRequestOptions = {},
): Promise<string> {
  return submitPasswordRecoveryRequest(AUTH_PATHS.passwordResetStart, input, 202, options);
}

export function confirmPasswordReset(
  input: PasswordResetConfirmInput,
  options: AuthRequestOptions = {},
): Promise<string> {
  return submitPasswordRecoveryRequest(AUTH_PATHS.passwordResetConfirm, input, 200, options);
}

export function googleSignInUrl(): string {
  try {
    return buildApiUrl(GOOGLE_START_PATH);
  } catch (error) {
    if (!(error instanceof ApiTransportError)) {
      throw error;
    }
    return "#google-sign-in-unavailable";
  }
}

export async function confirmGoogleLink(
  input: GoogleLinkConfirmInput,
  options: AuthRequestOptions = {},
): Promise<Account> {
  const { payload, response } = await postAuthJsonWithCsrf(
    AUTH_PATHS.googleLinkConfirm,
    input,
    options,
  );
  if (response.status === 200 && isAccount(payload)) {
    return payload;
  }

  const message = readApiMessage(payload);
  if (response.status === 400) {
    throw new AuthApiError(
      "validation",
      message ?? "Start Google sign-in again before linking.",
      readFieldErrors(payload),
    );
  }
  if (response.status === 401) {
    throw new AuthApiError(
      "credentials",
      message ?? "Enter the current password for this account.",
    );
  }
  if (response.status === 403) {
    throw new AuthApiError("csrf", "Your form expired. Please try again.");
  }
  if (response.status === 409) {
    throw new AuthApiError(
      "conflict",
      message ?? "This Google identity cannot be linked to that account.",
    );
  }
  if (response.status === 415) {
    throw new AuthApiError("unavailable", "The Google link request format was rejected.");
  }
  throw unavailableError();
}

export async function cancelGoogleLink(options: AuthRequestOptions = {}): Promise<void> {
  const { response } = await postAuthJsonWithCsrf(AUTH_PATHS.googleLinkCancel, undefined, options);
  if (response.status === 204) {
    return;
  }
  if (response.status === 403) {
    throw new AuthApiError("csrf", "Your form expired. Please try again.");
  }
  throw unavailableError();
}

export async function signOut(options: AuthRequestOptions = {}): Promise<void> {
  const { response } = await postAuthJsonWithCsrf(AUTH_PATHS.signOut, undefined, options);
  if (response.status === 204) {
    return;
  }
  if (response.status === 403) {
    throw new AuthApiError("csrf", "Your form expired. Please try again.");
  }
  throw unavailableError();
}
