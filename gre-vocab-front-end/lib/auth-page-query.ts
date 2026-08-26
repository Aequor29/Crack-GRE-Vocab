export type GoogleSignInStatus =
  | "cancelled"
  | "conflict"
  | "link-required"
  | "provider-error"
  | "unavailable";

const googleSignInStatuses = new Set<GoogleSignInStatus>([
  "cancelled",
  "conflict",
  "link-required",
  "provider-error",
  "unavailable",
]);

export function readGoogleSignInStatus(
  value: string | string[] | undefined,
): GoogleSignInStatus | undefined {
  return typeof value === "string" && googleSignInStatuses.has(value as GoogleSignInStatus)
    ? (value as GoogleSignInStatus)
    : undefined;
}

type PageSearchParameters = Record<string, string | string[] | undefined>;

export type PasswordResetCredentials = {
  token: string;
  uid: string;
};

function readRequiredSingleValue(value: string | string[] | undefined): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

export function readPasswordResetCredentials(
  parameters: PageSearchParameters,
): PasswordResetCredentials | null {
  const token = readRequiredSingleValue(parameters.token);
  const uid = readRequiredSingleValue(parameters.uid);
  return token && uid ? { token, uid } : null;
}
