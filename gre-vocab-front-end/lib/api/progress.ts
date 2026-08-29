import type {
  LearningInsights,
  LearningProgressSummary,
  ProgressError,
  ReviewRecallPeriod,
} from "@/lib/api/generated/schema.generated";
import { type ApiRequestOptions, ApiTransportError, getApiJson } from "@/lib/api/transport";

type OpenApiDocument = typeof import("../../../crackGreVocab/openapi.json");
type OpenApiPaths = OpenApiDocument["paths"];

const PROGRESS_SUMMARY_PATH = "/api/progress/summary/" as const satisfies keyof OpenApiPaths;
const PROGRESS_INSIGHTS_PATH = "/api/progress/insights/" as const satisfies keyof OpenApiPaths;
const CALENDAR_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

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
    isNonnegativeInteger(corpus.reviewing) &&
    isNonnegativeInteger(corpus.mastered) &&
    corpus.unseen + corpus.learning + corpus.reviewing + corpus.mastered === corpus.total;
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
  return validCorpus && validActionable && validToday;
}

function isDateString(value: unknown): value is string {
  return typeof value === "string" && CALENDAR_DATE_PATTERN.test(value);
}

function isRate(value: unknown): value is number | null {
  return value === null || (isNonnegativeInteger(value) && value <= 100);
}

function isReviewRecallPeriod(value: unknown): value is ReviewRecallPeriod {
  if (!value || typeof value !== "object") {
    return false;
  }
  const period = value as Partial<ReviewRecallPeriod>;
  return (
    isDateString(period.starts_on) &&
    isDateString(period.ends_on) &&
    isNonnegativeInteger(period.remembered) &&
    isNonnegativeInteger(period.answers) &&
    period.remembered <= period.answers &&
    isRate(period.rate_percent) &&
    typeof period.has_sufficient_data === "boolean"
  );
}

function isLearningInsights(value: unknown): value is LearningInsights {
  if (!value || typeof value !== "object") {
    return false;
  }
  const insights = value as Partial<LearningInsights>;
  const recall = insights.review_recall;
  const consistency = insights.consistency;
  const curve = insights.learning_curve;
  if (
    !isDateString(insights.as_of_date) ||
    typeof insights.timezone !== "string" ||
    !recall ||
    !isReviewRecallPeriod(recall.current) ||
    !isReviewRecallPeriod(recall.previous) ||
    !(
      recall.change_percentage_points === null || Number.isInteger(recall.change_percentage_points)
    ) ||
    !consistency ||
    !isDateString(consistency.calendar_starts_on) ||
    !isDateString(consistency.calendar_ends_on) ||
    !isNonnegativeInteger(consistency.current_streak_days) ||
    !Array.isArray(consistency.study_days) ||
    !Array.isArray(curve) ||
    curve.length !== 12
  ) {
    return false;
  }
  const validStudyDays = consistency.study_days.every(
    (day) =>
      isDateString(day.date) &&
      isNonnegativeInteger(day.answers) &&
      day.answers > 0 &&
      isNonnegativeInteger(day.words_practiced) &&
      day.words_practiced > 0 &&
      day.words_practiced <= day.answers,
  );
  const corpusTotals = new Set<number>();
  const validCurve = curve.every((week) => {
    const valid =
      isDateString(week.starts_on) &&
      isDateString(week.ends_on) &&
      isNonnegativeInteger(week.unseen) &&
      isNonnegativeInteger(week.learning) &&
      isNonnegativeInteger(week.reviewing) &&
      isNonnegativeInteger(week.mastered);
    if (valid) {
      corpusTotals.add(week.unseen + week.learning + week.reviewing + week.mastered);
    }
    return valid;
  });
  return validStudyDays && validCurve && corpusTotals.size === 1;
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

export async function getLearningInsights(
  timezone: string,
  options: ApiRequestOptions = {},
): Promise<LearningInsights> {
  const path = `${PROGRESS_INSIGHTS_PATH}?timezone=${encodeURIComponent(timezone)}`;
  try {
    const { payload, response } = await getApiJson(path, options);
    if (response.status === 200 && isLearningInsights(payload)) {
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
