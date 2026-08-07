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
 * * `due` - Due review
 * * `new` - New Word
 */
export type KindEnum = "due" | "new";

/**
 * * `available` - available
 * * `unavailable` - unavailable
 */
export type DatabaseEnum = "available" | "unavailable";

/** Describe a non-field API error. */
export interface ApiError {
  detail: string;
}

/** Describe malformed JSON or field-level account input errors. */
export interface AuthValidationError {
  detail?: string;
  email?: string[];
  display_name?: string[];
  password?: string[];
  non_field_errors?: string[];
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

export interface StudyPlanningError {
  detail: string;
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
  /**
   * @min 0
   * @max 32767
   */
  planned_new_word_count: number;
  /**
   * @min 0
   * @max 32767
   */
  item_count: number;
  /** @maxLength 64 */
  planner_version: string;
  /** @format date-time */
  created_at: string;
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
  detail?: string;
  new_word_target?: string[];
}
