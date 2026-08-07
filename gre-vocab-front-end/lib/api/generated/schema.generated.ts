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
 * * `ready` - ready
 * * `unavailable` - unavailable
 */
export type StatusEnum = "ready" | "unavailable";

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
  status: StatusEnum;
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
