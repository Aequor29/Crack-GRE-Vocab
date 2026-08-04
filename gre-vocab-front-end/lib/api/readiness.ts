import type { Readiness } from "@/lib/api/generated/schema.generated";

type OpenApiDocument = typeof import("../../../crackGreVocab/openapi.json");
type OpenApiPaths = OpenApiDocument["paths"];
type ReadinessResponseStatuses = keyof OpenApiPaths["/api/readiness/"]["get"]["responses"];
type IsExact<Actual, Expected> =
  (<Value>() => Value extends Actual ? 1 : 2) extends <Value>() => Value extends Expected ? 1 : 2
    ? true
    : false;

const READINESS_CONTRACT = {
  path: "/api/readiness/",
  responseStatusesMatch: true,
} as const satisfies {
  path: keyof OpenApiPaths;
  responseStatusesMatch: IsExact<ReadinessResponseStatuses, "200" | "503">;
};

const READINESS_PATH = READINESS_CONTRACT.path;

export type ReadinessResult = "ready" | "database-unavailable" | "backend-unavailable";

type ReadinessPayload = Readiness;

type CheckReadinessOptions = {
  fetcher?: typeof fetch;
  signal?: AbortSignal;
};

function configuredApiOrigin(): string | null {
  const configuredUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!configuredUrl) {
    return null;
  }

  try {
    const url = new URL(configuredUrl);
    if (
      !["http:", "https:"].includes(url.protocol) ||
      url.pathname !== "/" ||
      url.search ||
      url.hash
    ) {
      return null;
    }
    return url.origin;
  } catch {
    return null;
  }
}

function isReadinessPayload(value: unknown): value is ReadinessPayload {
  if (!value || typeof value !== "object") {
    return false;
  }

  const payload = value as Partial<ReadinessPayload>;
  return (
    (payload.status === "ready" || payload.status === "unavailable") &&
    (payload.database === "available" || payload.database === "unavailable")
  );
}

function isAbortError(error: unknown, signal?: AbortSignal): boolean {
  return signal?.aborted === true || (error instanceof DOMException && error.name === "AbortError");
}

export async function checkReadiness({
  fetcher = fetch,
  signal,
}: CheckReadinessOptions = {}): Promise<ReadinessResult> {
  const apiOrigin = configuredApiOrigin();
  if (!apiOrigin) {
    return "backend-unavailable";
  }

  try {
    const response = await fetcher(`${apiOrigin}${READINESS_PATH}`, {
      cache: "no-store",
      credentials: "omit",
      headers: { Accept: "application/json" },
      method: "GET",
      signal,
    });
    const payload: unknown = await response.json();

    if (!isReadinessPayload(payload)) {
      return "backend-unavailable";
    }
    if (response.status === 200 && payload.status === "ready" && payload.database === "available") {
      return "ready";
    }
    if (
      response.status === 503 &&
      payload.status === "unavailable" &&
      payload.database === "unavailable"
    ) {
      return "database-unavailable";
    }
    return "backend-unavailable";
  } catch (error) {
    if (isAbortError(error, signal)) {
      throw error;
    }
    return "backend-unavailable";
  }
}
