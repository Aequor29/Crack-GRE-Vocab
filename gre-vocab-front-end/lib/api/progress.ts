import type {
  LearningProgressSummary,
  ProgressError,
  RecentRecallOutcome,
} from "@/lib/api/generated/schema.generated";
import { type ApiRequestOptions, ApiTransportError, getApiJson } from "@/lib/api/transport";

type OpenApiDocument = typeof import("../../../crackGreVocab/openapi.json");
type OpenApiPaths = OpenApiDocument["paths"];

const PROGRESS_SUMMARY_PATH = "/api/progress/summary/" as const satisfies keyof OpenApiPaths;

export type ProgressErrorKind = "unauthenticated" | "unavailable" | "validation";

export class ProgressApiError extends Error {
  readonly code: string | null;
  readonly kind: ProgressErrorKind;
  readonly retryable: boolean;

  constructor(
    kind: ProgressErrorKind,
    message: string,
    options: { code?: string | null; retryable?: boolean } = {},
  ) {
    super(message);
    this.name = "ProgressApiError";
    this.code = options.code ?? null;
    this.kind = kind;
    this.retryable = options.retryable ?? false;
  }
}

function unavailableError(options: { code?: string | null; retryable?: boolean } = {}) {
  return new ProgressApiError("unavailable", "We couldn't load your progress. Please try again.", {
    ...options,
  });
}

function isNonnegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function isRecentRecallOutcome(value: unknown): value is RecentRecallOutcome {
  if (!value || typeof value !== "object") {
    return false;
  }
  const outcome = value as Partial<RecentRecallOutcome>;
  return (
    typeof outcome.word_id === "string" &&
    typeof outcome.term === "string" &&
    (outcome.rating === "remembered" || outcome.rating === "forgot") &&
    (outcome.phase === "learning" ||
      outcome.phase === "review" ||
      outcome.phase === "relearning") &&
    typeof outcome.next_due_at === "string" &&
    typeof outcome.occurred_at === "string"
  );
}

function isLearningProgressSummary(value: unknown): value is LearningProgressSummary {
  if (!value || typeof value !== "object") {
    return false;
  }
  const summary = value as Partial<LearningProgressSummary>;
  const corpus = summary.corpus;
  const actionable = summary.actionable;
  const today = summary.today;
  if (!corpus || !actionable || !today) {
    return false;
  }
  const validCorpus =
    typeof corpus.version === "string" &&
    isNonnegativeInteger(corpus.total) &&
    isNonnegativeInteger(corpus.unseen) &&
    isNonnegativeInteger(corpus.learning) &&
    isNonnegativeInteger(corpus.review) &&
    corpus.unseen + corpus.learning + corpus.review === corpus.total;
  const seen = corpus.total - corpus.unseen;
  const validActionable =
    isNonnegativeInteger(actionable.due_now) &&
    isNonnegativeInteger(actionable.due_today) &&
    actionable.due_now <= actionable.due_today &&
    actionable.due_today <= seen &&
    typeof actionable.has_active_session === "boolean";
  const validToday =
    typeof today.date === "string" &&
    typeof today.timezone === "string" &&
    isNonnegativeInteger(today.sessions_started) &&
    isNonnegativeInteger(today.sessions_completed) &&
    isNonnegativeInteger(today.answers) &&
    isNonnegativeInteger(today.remembered) &&
    isNonnegativeInteger(today.forgot) &&
    today.remembered + today.forgot === today.answers;
  return (
    validCorpus &&
    validActionable &&
    validToday &&
    Array.isArray(summary.recent_outcomes) &&
    summary.recent_outcomes.length <= 5 &&
    summary.recent_outcomes.every(isRecentRecallOutcome)
  );
}

function readErrorPayload(payload: unknown): Partial<ProgressError> {
  return payload && typeof payload === "object" ? (payload as Partial<ProgressError>) : {};
}

function responseError(response: Response, payload: unknown): ProgressApiError {
  const error = readErrorPayload(payload);
  const code = typeof error.code === "string" ? error.code : null;
  if (response.status === 400) {
    return new ProgressApiError("validation", "Your timezone could not be used.", { code });
  }
  if (response.status === 401 || response.status === 403) {
    return new ProgressApiError(
      "unauthenticated",
      "Your sign-in expired. Sign in again to continue.",
      { code },
    );
  }
  if (response.status === 503) {
    return unavailableError({ code, retryable: true });
  }
  return unavailableError({ code });
}

export async function getLearningProgress(
  timezone: string,
  options: ApiRequestOptions = {},
): Promise<LearningProgressSummary> {
  const path = `${PROGRESS_SUMMARY_PATH}?timezone=${encodeURIComponent(timezone)}`;
  try {
    const { payload, response } = await getApiJson(path, options);
    if (response.status === 200 && isLearningProgressSummary(payload)) {
      return payload;
    }
    throw responseError(response, payload);
  } catch (error) {
    if (error instanceof ApiTransportError) {
      throw unavailableError({ retryable: true });
    }
    throw error;
  }
}
