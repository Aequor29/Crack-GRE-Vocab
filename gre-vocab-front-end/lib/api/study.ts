import type {
  RecordRecallAnswerRequest,
  StudyAnswerResponse,
  StudyPlanningError,
  StudySession,
} from "@/lib/api/generated/schema.generated";
import {
  type ApiJsonResult,
  type ApiRequestOptions,
  ApiTransportError,
  getApiJson,
  postApiJsonWithCsrf,
} from "@/lib/api/transport";

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

type StudyErrorDefinition = {
  kind: StudyErrorKind;
  message: string;
  retryable: boolean;
};

const studyErrorsByCode = {
  authentication_required: {
    kind: "unauthenticated",
    message: "Your sign-in expired. Sign in again to continue.",
    retryable: false,
  },
  csrf_failed: {
    kind: "csrf",
    message: "Your study request expired. Please try again.",
    retryable: true,
  },
  invalid_json: {
    kind: "validation",
    message: "The study request was not valid.",
    retryable: false,
  },
  study_corpus_unavailable: {
    kind: "conflict",
    message: "No vocabulary corpus is currently available for study.",
    retryable: false,
  },
  study_item_already_answered: {
    kind: "conflict",
    message: "This card was already answered. Reloading your progress is safe.",
    retryable: false,
  },
  study_item_not_found: {
    kind: "not-found",
    message: "This study card is no longer available. Reloading your progress is safe.",
    retryable: false,
  },
  study_item_out_of_order: {
    kind: "conflict",
    message: "Your study session advanced elsewhere. Reloading it is safe.",
    retryable: false,
  },
  study_no_eligible_items: {
    kind: "conflict",
    message: "No vocabulary items are ready for a new study session.",
    retryable: false,
  },
  study_request_id_reused: {
    kind: "conflict",
    message: "This saved answer no longer matches your study progress.",
    retryable: false,
  },
  study_session_inactive: {
    kind: "conflict",
    message: "This study session is no longer active. Reloading your progress is safe.",
    retryable: false,
  },
  study_session_not_found: {
    kind: "not-found",
    message: "No active study session exists.",
    retryable: false,
  },
  study_temporarily_unavailable: {
    kind: "unavailable",
    message: "Study is temporarily unavailable. Please try again.",
    retryable: true,
  },
  unsupported_media_type: {
    kind: "validation",
    message: "The study request format was not supported.",
    retryable: false,
  },
  validation_error: {
    kind: "validation",
    message: "Check the study request and try again.",
    retryable: false,
  },
} as const satisfies Record<string, StudyErrorDefinition>;

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

export type StudyRequestOptions = ApiRequestOptions;

function createStudyUnavailableError(): StudyApiError {
  return new StudyApiError("unavailable", "Study is temporarily unavailable. Please try again.", {
    retryable: true,
  });
}

function throwStudyTransportError(error: unknown): never {
  if (error instanceof ApiTransportError) {
    throw createStudyUnavailableError();
  }
  throw error;
}

async function getStudyJson(
  path: keyof OpenApiPaths,
  options: StudyRequestOptions,
): Promise<ApiJsonResult> {
  try {
    return await getApiJson(path, options);
  } catch (error) {
    throwStudyTransportError(error);
  }
}

async function postStudyJsonWithCsrf(
  path: string,
  body: unknown,
  options: StudyRequestOptions,
): Promise<ApiJsonResult> {
  try {
    return await postApiJsonWithCsrf(CSRF_PATH, path, body, options);
  } catch (error) {
    throwStudyTransportError(error);
  }
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isStudySense(value: unknown): boolean {
  if (!value || typeof value !== "object") {
    return false;
  }
  const sense = value as Record<string, unknown>;
  return (
    isNumber(sense.position) &&
    (sense.part_of_speech === undefined || isString(sense.part_of_speech)) &&
    isString(sense.definition) &&
    isString(sense.example)
  );
}

function isStudySessionItem(value: unknown): boolean {
  if (!value || typeof value !== "object") {
    return false;
  }
  const item = value as Record<string, unknown>;
  return (
    isString(item.id) &&
    isNumber(item.position) &&
    (item.kind === "due" || item.kind === "new") &&
    isString(item.word_id) &&
    isString(item.term) &&
    isString(item.pronunciation) &&
    Array.isArray(item.senses) &&
    item.senses.every(isStudySense)
  );
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
    isString(session.corpus_version) &&
    isNumber(session.new_word_target) &&
    isNumber(session.planned_new_word_count) &&
    isNumber(session.item_count) &&
    isString(session.planner_version) &&
    isString(session.created_at) &&
    (session.ended_at === undefined || session.ended_at === null || isString(session.ended_at)) &&
    isNumber(session.answered_count) &&
    isNumber(session.remaining_count) &&
    Array.isArray(session.items) &&
    session.items.every(isStudySessionItem) &&
    (session.current_item === null || isStudySessionItem(session.current_item))
  );
}

function isRecallAnswer(value: unknown): boolean {
  if (!value || typeof value !== "object") {
    return false;
  }
  const answer = value as Record<string, unknown>;
  return (
    isString(answer.id) &&
    isString(answer.item_id) &&
    isString(answer.client_request_id) &&
    (answer.rating === "remembered" || answer.rating === "forgot") &&
    isString(answer.submitted_at) &&
    isString(answer.accepted_at)
  );
}

function isRecallOutcome(value: unknown): boolean {
  if (!value || typeof value !== "object") {
    return false;
  }
  const outcome = value as Record<string, unknown>;
  return (
    isString(outcome.id) &&
    isNumber(outcome.review_number) &&
    isString(outcome.scheduler_version) &&
    isString(outcome.previous_phase) &&
    isString(outcome.next_phase) &&
    (outcome.previous_due_at === undefined ||
      outcome.previous_due_at === null ||
      isString(outcome.previous_due_at)) &&
    isString(outcome.next_due_at) &&
    isString(outcome.occurred_at)
  );
}

function isStudyAnswerResponse(value: unknown): value is StudyAnswerResponse {
  if (!value || typeof value !== "object") {
    return false;
  }
  const answerResponse = value as Partial<StudyAnswerResponse>;
  return (
    isRecallAnswer(answerResponse.answer) &&
    isRecallOutcome(answerResponse.outcome) &&
    typeof answerResponse.replayed === "boolean" &&
    isStudySession(answerResponse.session)
  );
}

function parseStudyErrorPayload(payload: unknown): Partial<StudyPlanningError> {
  return payload && typeof payload === "object" ? (payload as Partial<StudyPlanningError>) : {};
}

function createStudyErrorFromResponse(response: Response, payload: unknown): StudyApiError {
  const error = parseStudyErrorPayload(payload);
  const code = isString(error.code) ? error.code : null;
  const currentItemId = isString(error.current_item_id) ? error.current_item_id : null;
  const definition =
    code && Object.hasOwn(studyErrorsByCode, code)
      ? studyErrorsByCode[code as keyof typeof studyErrorsByCode]
      : undefined;
  if (definition) {
    return new StudyApiError(definition.kind, definition.message, {
      code,
      currentItemId,
      retryable: definition.retryable,
    });
  }
  if (response.status === 400) {
    return new StudyApiError("validation", "The study request was not valid.", { code });
  }
  if (response.status === 401) {
    return new StudyApiError(
      "unauthenticated",
      "Your sign-in expired. Sign in again to continue.",
      {
        code,
      },
    );
  }
  if (response.status === 403) {
    return new StudyApiError(
      "unauthenticated",
      "Your sign-in expired. Sign in again to continue.",
      {
        code,
      },
    );
  }
  if (response.status === 404) {
    return new StudyApiError("not-found", "The requested study progress was not found.", { code });
  }
  if (response.status === 409) {
    return new StudyApiError("conflict", "Your study progress changed. Reload it and try again.", {
      code,
      currentItemId,
    });
  }
  if (response.status === 503) {
    return new StudyApiError("unavailable", "Study is temporarily unavailable. Please try again.", {
      code,
      retryable: true,
    });
  }
  return createStudyUnavailableError();
}

export async function getActiveStudySession(
  options: StudyRequestOptions = {},
): Promise<StudySession | null> {
  const { payload, response } = await getStudyJson(STUDY_CONTRACT.active, options);
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
  const { payload, response } = await postStudyJsonWithCsrf(
    STUDY_CONTRACT.sessions,
    { new_word_target: newWordTarget },
    options,
  );
  if ((response.status === 200 || response.status === 201) && isStudySession(payload)) {
    return payload;
  }
  throw createStudyErrorFromResponse(response, payload);
}

export async function submitRecallAnswer(
  input: RecallAnswerInput,
  options: StudyRequestOptions = {},
): Promise<StudyAnswerResponse> {
  const path = STUDY_CONTRACT.answer
    .replace("{session_id}", input.sessionId)
    .replace("{item_id}", input.itemId);
  const { payload, response } = await postStudyJsonWithCsrf(
    path,
    {
      client_request_id: input.client_request_id,
      rating: input.rating,
    } satisfies RecordRecallAnswerRequest,
    options,
  );
  if ((response.status === 200 || response.status === 201) && isStudyAnswerResponse(payload)) {
    return payload;
  }
  throw createStudyErrorFromResponse(response, payload);
}
