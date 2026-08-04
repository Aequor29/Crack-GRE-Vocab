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
