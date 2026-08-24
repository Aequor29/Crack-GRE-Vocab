import type { Readiness } from "@/lib/api/generated/schema.generated";
import { type ApiRequestOptions, ApiTransportError, getApiJson } from "@/lib/api/transport";

type OpenApiDocument = typeof import("../../../crackGreVocab/openapi.json");
type OpenApiPaths = OpenApiDocument["paths"];
const READINESS_PATH = "/api/readiness/" as const satisfies keyof OpenApiPaths;

export type ReadinessResult = "ready" | "database-unavailable" | "backend-unavailable";

type ReadinessPayload = Readiness;

type CheckReadinessOptions = ApiRequestOptions;

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

export async function checkReadiness(
  options: CheckReadinessOptions = {},
): Promise<ReadinessResult> {
  try {
    const { payload, response } = await getApiJson(READINESS_PATH, options, "omit");

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
    if (error instanceof ApiTransportError) {
      return "backend-unavailable";
    }
    throw error;
  }
}
