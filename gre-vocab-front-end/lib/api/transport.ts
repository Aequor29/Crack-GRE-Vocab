export type ApiRequestOptions = {
  fetcher?: typeof fetch;
  signal?: AbortSignal;
};

export type ApiJsonResult = {
  payload: unknown;
  response: Response;
};

type ApiTransportErrorKind = "configuration" | "csrf-token" | "network";

export class ApiTransportError extends Error {
  readonly kind: ApiTransportErrorKind;

  constructor(kind: ApiTransportErrorKind) {
    super(`API transport failed: ${kind}`);
    this.name = "ApiTransportError";
    this.kind = kind;
  }
}

type JsonRequest = {
  body?: unknown;
  csrfToken?: string;
  credentials: "include" | "omit";
  method: "GET" | "POST";
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

export function buildApiUrl(path: string): string {
  const origin = configuredApiOrigin();
  if (!origin) {
    throw new ApiTransportError("configuration");
  }
  return `${origin}${path}`;
}

function isAbortError(error: unknown, signal?: AbortSignal): boolean {
  return signal?.aborted === true || (error instanceof DOMException && error.name === "AbortError");
}

async function readJson(response: Response, signal?: AbortSignal): Promise<unknown> {
  try {
    return await response.json();
  } catch (error) {
    if (isAbortError(error, signal)) {
      throw error;
    }
    return null;
  }
}

async function requestApiJson(
  path: string,
  request: JsonRequest,
  { fetcher = fetch, signal }: ApiRequestOptions,
): Promise<ApiJsonResult> {
  const hasBody = request.body !== undefined;
  const url = buildApiUrl(path);
  const body = hasBody ? JSON.stringify(request.body) : undefined;
  let response: Response;
  try {
    response = await fetcher(url, {
      ...(body === undefined ? {} : { body }),
      cache: "no-store",
      credentials: request.credentials,
      headers: {
        Accept: "application/json",
        ...(hasBody ? { "Content-Type": "application/json" } : {}),
        ...(request.csrfToken ? { "X-CSRFToken": request.csrfToken } : {}),
      },
      method: request.method,
      ...(signal ? { signal } : {}),
    });
  } catch (error) {
    if (isAbortError(error, signal) || error instanceof ApiTransportError) {
      throw error;
    }
    throw new ApiTransportError("network");
  }
  return {
    payload: response.status === 204 ? null : await readJson(response, signal),
    response,
  };
}

export function getApiJson(
  path: string,
  options: ApiRequestOptions = {},
  credentials: "include" | "omit" = "include",
): Promise<ApiJsonResult> {
  return requestApiJson(path, { credentials, method: "GET" }, options);
}

export async function postApiJsonWithCsrf(
  csrfPath: string,
  path: string,
  body: unknown | undefined,
  options: ApiRequestOptions = {},
): Promise<ApiJsonResult> {
  const csrf = await getApiJson(csrfPath, options);
  const token =
    csrf.payload && typeof csrf.payload === "object"
      ? (csrf.payload as { csrf_token?: unknown }).csrf_token
      : null;
  if (csrf.response.status !== 200 || typeof token !== "string") {
    throw new ApiTransportError("csrf-token");
  }

  return requestApiJson(
    path,
    {
      body,
      csrfToken: token,
      credentials: "include",
      method: "POST",
    },
    options,
  );
}
