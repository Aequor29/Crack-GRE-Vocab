import type {
  RecordRecallAnswerRequest,
  StudyAnswerResponse,
  StudyPlanningError,
  StudySession,
} from "@/lib/api/generated/schema.generated";
import { configuredApiOrigin } from "@/lib/api/origin";

type OpenApiDocument = typeof import("../../../crackGreVocab/openapi.json");
type OpenApiPaths = OpenApiDocument["paths"];

const STUDY_CONTRACT = {
  active: "/api/study/sessions/active/",
  answer: "/api/study/sessions/{session_id}/items/{item_id}/answer/",
  sessions: "/api/study/sessions/",
} as const satisfies {
  active: keyof OpenApiPaths;
  answer: keyof OpenApiPaths;
  sessions: keyof OpenApiPaths;
};

const CSRF_PATH = "/api/auth/csrf/" as const satisfies keyof OpenApiPaths;

export type RecallRating = RecordRecallAnswerRequest["rating"];

export type RecallAnswerInput = RecordRecallAnswerRequest & {
  itemId: string;
  sessionId: string;
};

export type StudyErrorKind =
  | "conflict"
  | "csrf"
  | "not-found"
  | "unauthenticated"
  | "unavailable"
  | "validation";

export class StudyApiError extends Error {
  readonly code: string | null;
  readonly currentItemId: string | null;
  readonly kind: StudyErrorKind;
  readonly retryable: boolean;

  constructor(
    kind: StudyErrorKind,
    message: string,
    options: {
      code?: string | null;
      currentItemId?: string | null;
      retryable?: boolean;
    } = {},
  ) {
    super(message);
    this.name = "StudyApiError";
    this.code = options.code ?? null;
    this.currentItemId = options.currentItemId ?? null;
    this.kind = kind;
    this.retryable = options.retryable ?? false;
  }
}

export type StudyRequestOptions = {
  fetcher?: typeof fetch;
  signal?: AbortSignal;
};

function buildStudyApiUrl(path: string): string {
  const origin = configuredApiOrigin();
  if (!origin) {
    throw createStudyUnavailableError("The local API is not configured.");
  }
  return `${origin}${path}`;
}

function isAbortError(error: unknown, signal?: AbortSignal): boolean {
  return signal?.aborted === true || (error instanceof DOMException && error.name === "AbortError");
}

function createStudyUnavailableError(message = "The local backend is unavailable."): StudyApiError {
  return new StudyApiError(
    "unavailable",
    `${message} Try again when Django and PostgreSQL are ready.`,
    {
      retryable: true,
    },
  );
}

async function requestStudyApi(
  path: string,
  init: RequestInit,
  { fetcher = fetch, signal }: StudyRequestOptions,
): Promise<Response> {
  try {
    return await fetcher(buildStudyApiUrl(path), { ...init, signal });
  } catch (error) {
    if (isAbortError(error, signal) || error instanceof StudyApiError) {
      throw error;
    }
    throw createStudyUnavailableError();
  }
}

async function readResponseJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isStudySession(value: unknown): value is StudySession {
  if (!value || typeof value !== "object") {
    return false;
  }
  const session = value as Partial<StudySession>;
  return (
    isString(session.id) &&
    (session.status === "active" ||
      session.status === "completed" ||
      session.status === "abandoned") &&
    typeof session.item_count === "number" &&
    typeof session.answered_count === "number" &&
    typeof session.remaining_count === "number" &&
    Array.isArray(session.items) &&
    (session.current_item === null ||
      (Boolean(session.current_item) && isString(session.current_item?.id)))
  );
}

function isStudyAnswerResponse(value: unknown): value is StudyAnswerResponse {
  if (!value || typeof value !== "object") {
    return false;
  }
  const response = value as Partial<StudyAnswerResponse>;
  return (
    Boolean(response.answer) &&
    isString(response.answer?.id) &&
    Boolean(response.outcome) &&
    isString(response.outcome?.id) &&
    typeof response.replayed === "boolean" &&
    isStudySession(response.session)
  );
}

function parseStudyErrorPayload(payload: unknown): Partial<StudyPlanningError> {
  return payload && typeof payload === "object" ? (payload as Partial<StudyPlanningError>) : {};
}

function createStudyErrorFromResponse(response: Response, payload: unknown): StudyApiError {
  const error = parseStudyErrorPayload(payload);
  const detail = isString(error.detail)
    ? error.detail
    : "The study request could not be completed.";
  if (response.status === 400) {
    return new StudyApiError("validation", detail);
  }
  if (response.status === 401) {
    return new StudyApiError("unauthenticated", "Your sign-in expired. Sign in again to continue.");
  }
  if (response.status === 403) {
    if (detail.startsWith("CSRF Failed:")) {
      return new StudyApiError("csrf", "Your study request expired. Please try again.", {
        retryable: true,
      });
    }
    return new StudyApiError("unauthenticated", "Your sign-in expired. Sign in again to continue.");
  }
  if (response.status === 404) {
    return new StudyApiError("not-found", detail, { code: error.code });
  }
  if (response.status === 409) {
    return new StudyApiError("conflict", detail, {
      code: error.code,
      currentItemId: error.current_item_id,
    });
  }
  if (response.status === 503) {
    return createStudyUnavailableError(detail);
  }
  return createStudyUnavailableError();
}

async function fetchFreshCsrfToken(options: StudyRequestOptions): Promise<string> {
  const response = await requestStudyApi(
    CSRF_PATH,
    {
      cache: "no-store",
      credentials: "include",
      headers: { Accept: "application/json" },
      method: "GET",
    },
    options,
  );
  const payload = await readResponseJson(response);
  const token =
    payload && typeof payload === "object"
      ? (payload as { csrf_token?: unknown }).csrf_token
      : null;
  if (response.status !== 200 || !isString(token)) {
    throw createStudyUnavailableError("A fresh form token could not be obtained.");
  }
  return token;
}

export async function getActiveStudySession(
  options: StudyRequestOptions = {},
): Promise<StudySession | null> {
  const response = await requestStudyApi(
    STUDY_CONTRACT.active,
    {
      cache: "no-store",
      credentials: "include",
      headers: { Accept: "application/json" },
      method: "GET",
    },
    options,
  );
  const payload = await readResponseJson(response);
  if (response.status === 200 && isStudySession(payload)) {
    return payload;
  }
  if (response.status === 404) {
    return null;
  }
  throw createStudyErrorFromResponse(response, payload);
}

export async function createStudySession(
  newWordTarget: number,
  options: StudyRequestOptions = {},
): Promise<StudySession> {
  const token = await fetchFreshCsrfToken(options);
  const response = await requestStudyApi(
    STUDY_CONTRACT.sessions,
    {
      body: JSON.stringify({ new_word_target: newWordTarget }),
      cache: "no-store",
      credentials: "include",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRFToken": token,
      },
      method: "POST",
    },
    options,
  );
  const payload = await readResponseJson(response);
  if ((response.status === 200 || response.status === 201) && isStudySession(payload)) {
    return payload;
  }
  throw createStudyErrorFromResponse(response, payload);
}

export async function submitRecallAnswer(
  input: RecallAnswerInput,
  options: StudyRequestOptions = {},
): Promise<StudyAnswerResponse> {
  const token = await fetchFreshCsrfToken(options);
  const path = STUDY_CONTRACT.answer
    .replace("{session_id}", input.sessionId)
    .replace("{item_id}", input.itemId);
  const response = await requestStudyApi(
    path,
    {
      body: JSON.stringify({
        client_request_id: input.client_request_id,
        rating: input.rating,
      } satisfies RecordRecallAnswerRequest),
      cache: "no-store",
      credentials: "include",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRFToken": token,
      },
      method: "POST",
    },
    options,
  );
  const payload = await readResponseJson(response);
  if ((response.status === 200 || response.status === 201) && isStudyAnswerResponse(payload)) {
    return payload;
  }
  throw createStudyErrorFromResponse(response, payload);
}
