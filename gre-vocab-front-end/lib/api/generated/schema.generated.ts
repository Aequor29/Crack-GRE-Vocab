/* eslint-disable */
/* tslint:disable */
// @ts-nocheck
/*
 * ---------------------------------------------------------------
 * ## THIS FILE WAS GENERATED VIA SWAGGER-TYPESCRIPT-API        ##
 * ##                                                           ##
 * ## AUTHOR: acacode                                           ##
 * ## SOURCE: https://github.com/acacode/swagger-typescript-api ##
 * ---------------------------------------------------------------
 */

/**
 * * `active` - Active
 * * `completed` - Completed
 * * `abandoned` - Abandoned
 */
export type StudySessionStatusEnum = "active" | "completed" | "abandoned";

/**
 * * `ready` - ready
 * * `unavailable` - unavailable
 */
export type ReadinessStatusEnum = "ready" | "unavailable";

/**
 * * `remembered` - Remembered
 * * `forgot` - Forgot
 */
export type RatingEnum = "remembered" | "forgot";

/**
 * * `due` - Due review
 * * `new` - New Word
 */
export type KindEnum = "due" | "new";

/**
 * * `available` - available
 * * `unavailable` - unavailable
 */
export type DatabaseEnum = "available" | "unavailable";

export interface ActionableProgress {
  /** @min 0 */
  due_now: number;
  /** @min 0 */
  due_today: number;
  has_active_session: boolean;
}

/** Describe an API response carrying one human-readable message. */
export interface ApiMessage {
  detail: string;
}

/** Describe malformed JSON or field-level account input errors. */
export interface AuthValidationError {
  detail?: string;
  email?: string[];
  display_name?: string[];
  password?: string[];
  token?: string[];
  uid?: string[];
  non_field_errors?: string[];
}

export interface CorpusProgress {
  version: string;
  /** @min 0 */
  total: number;
  /** @min 0 */
  unseen: number;
  /** @min 0 */
  learning: number;
  /** @min 0 */
  review: number;
}

export interface CreateStudySessionRequest {
  /**
   * @min 0
   * @max 20
   */
  new_word_target: number;
}

/** Return a masked CSRF token for one unsafe request. */
export interface CsrfToken {
  csrf_token: string;
}

/** Validate password proof for an explicitly pending Google link. */
export interface GoogleLinkConfirmRequest {
  /** @minLength 1 */
  password: string;
}

/** Return the public portion of the current learner account. */
export interface LearnerAccount {
  id: number;
  /**
   * Email address
   * @format email
   */
  email: string;
  display_name: string;
}

export interface LearningInsights {
  /** @format date */
  as_of_date: string;
  timezone: string;
  review_recall: ReviewRecall;
  consistency: StudyConsistency;
  learning_curve: WeeklyLearningCurvePoint[];
}

export interface LearningProgressSummary {
  corpus: CorpusProgress;
  actionable: ActionableProgress;
  today: TodayProgress;
}

/** Validate the opaque identity, token, and replacement password shape. */
export interface PasswordResetConfirmRequest {
  /**
   * @minLength 1
   * @maxLength 128
   */
  uid: string;
  /**
   * @minLength 1
   * @maxLength 256
   */
  token: string;
  /** @minLength 1 */
  password: string;
}

/** Validate a non-enumerating password-recovery request. */
export interface PasswordResetStartRequest {
  /**
   * @format email
   * @minLength 1
   * @maxLength 254
   */
  email: string;
}

export interface ProgressError {
  code: string;
  detail: string;
  retryable?: boolean;
}

/** Describe the stable ready or database-unavailable response shape. */
export interface Readiness {
  /**
   * * `ready` - ready
   * * `unavailable` - unavailable
   */
  status: ReadinessStatusEnum;
  /**
   * * `available` - available
   * * `unavailable` - unavailable
   */
  database: DatabaseEnum;
}

export interface RecallAnswer {
  /** @format uuid */
  id: string;
  /** @format uuid */
  item_id: string;
  /** @format uuid */
  client_request_id: string;
  /**
   * * `remembered` - Remembered
   * * `forgot` - Forgot
   */
  rating: RatingEnum;
  /** @format date-time */
  submitted_at: string;
  /** @format date-time */
  accepted_at: string;
}

export interface RecallOutcome {
  /** @format uuid */
  id: string;
  /**
   * @min 0
   * @max 2147483647
   */
  review_number: number;
  /** @maxLength 64 */
  scheduler_version: string;
  previous_phase: string;
  next_phase: string;
  /** @format date-time */
  previous_due_at?: string | null;
  /** @format date-time */
  next_due_at: string;
  /** @format date-time */
  occurred_at: string;
}

export interface RecordRecallAnswerRequest {
  /** @format uuid */
  client_request_id: string;
  /**
   * * `remembered` - Remembered
   * * `forgot` - Forgot
   */
  rating: RatingEnum;
}

export interface ReviewRecall {
  current: ReviewRecallPeriod;
  previous: ReviewRecallPeriod;
  change_percentage_points: number | null;
}

export interface ReviewRecallPeriod {
  /** @format date */
  starts_on: string;
  /** @format date */
  ends_on: string;
  /** @min 0 */
  remembered: number;
  /** @min 0 */
  answers: number;
  /**
   * @min 0
   * @max 100
   */
  rate_percent: number | null;
  has_sufficient_data: boolean;
}

/** Describe the database-independent service document. */
export interface ServiceIndex {
  service: string;
}

/** Validate the credentials supplied for a new server session. */
export interface SignInRequest {
  /**
   * @format email
   * @minLength 1
   * @maxLength 254
   */
  email: string;
  /** @minLength 1 */
  password: string;
}

/** Validate and create a clean-rebuild learner account. */
export interface SignUpRequest {
  /**
   * @format email
   * @minLength 1
   * @maxLength 254
   */
  email: string;
  /**
   * @minLength 1
   * @maxLength 80
   */
  display_name: string;
  /** @minLength 1 */
  password: string;
}

export interface StudyAnswerResponse {
  answer: RecallAnswer;
  outcome: RecallOutcome;
  session: StudySession;
  replayed: boolean;
}

export interface StudyConsistency {
  /** @format date */
  calendar_starts_on: string;
  /** @format date */
  calendar_ends_on: string;
  /** @min 0 */
  current_streak_days: number;
  study_days: StudyDay[];
}

export interface StudyDay {
  /** @format date */
  date: string;
  /** @min 1 */
  answers: number;
  /** @min 1 */
  words_practiced: number;
}

export interface StudyPlanningError {
  code: string;
  detail: string;
  /** @format uuid */
  current_item_id?: string;
  retryable?: boolean;
}

export interface StudySense {
  /**
   * @min 0
   * @max 32767
   */
  position: number;
  /** @maxLength 32 */
  part_of_speech?: string;
  definition: string;
  example: string;
}

export interface StudySession {
  /** @format uuid */
  id: string;
  /**
   * * `active` - Active
   * * `completed` - Completed
   * * `abandoned` - Abandoned
   */
  status: StudySessionStatusEnum;
  corpus_version: string;
  /**
   * @min 0
   * @max 32767
   */
  new_word_target: number;
  /** Derive how many persisted items introduce new Words. */
  planned_new_word_count: number;
  /** Derive total progress from the persisted session items. */
  item_count: number;
  /** @maxLength 64 */
  planner_version: string;
  /** @format date-time */
  created_at: string;
  /** @format date-time */
  ended_at?: string | null;
  /** Return how many planned items have accepted answers. */
  answered_count: number;
  /** Return how many planned items still need an accepted answer. */
  remaining_count: number;
  current_item: StudySessionItem | null;
  items: StudySessionItem[];
}

export interface StudySessionItem {
  /** @format uuid */
  id: string;
  /**
   * @min 0
   * @max 32767
   */
  position: number;
  /**
   * * `due` - Due review
   * * `new` - New Word
   */
  kind: KindEnum;
  /** @format uuid */
  word_id: string;
  term: string;
  pronunciation: string;
  senses: StudySense[];
}

export interface StudyValidationError {
  code: string;
  detail?: string;
  client_request_id?: string[];
  new_word_target?: string[];
  rating?: string[];
}

export interface TodayProgress {
  /** @format date */
  date: string;
  timezone: string;
  /** @min 0 */
  sessions_started: number;
  /** @min 0 */
  sessions_completed: number;
  /** @min 0 */
  answers: number;
  /** @min 0 */
  remembered: number;
  /** @min 0 */
  forgot: number;
}

export interface WeeklyLearningCurvePoint {
  /** @format date */
  starts_on: string;
  /** @format date */
  ends_on: string;
  /** @min 0 */
  unseen: number;
  /** @min 0 */
  learning: number;
  /** @min 0 */
  review: number;
}
