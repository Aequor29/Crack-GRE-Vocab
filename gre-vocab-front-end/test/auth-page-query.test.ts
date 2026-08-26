import { describe, expect, it } from "vitest";

import { readGoogleSignInStatus, readPasswordResetCredentials } from "@/lib/auth-page-query";

describe("authentication page query adapters", () => {
  it("accepts one known Google status and ignores missing, repeated, or unknown values", () => {
    expect(readGoogleSignInStatus("link-required")).toBe("link-required");
    expect(readGoogleSignInStatus(undefined)).toBeUndefined();
    expect(readGoogleSignInStatus(["cancelled", "conflict"])).toBeUndefined();
    expect(readGoogleSignInStatus("unexpected-provider-state")).toBeUndefined();
  });

  it("accepts one reset credential pair and rejects missing or repeated values", () => {
    expect(
      readPasswordResetCredentials({
        token: "opaque-token",
        tracking: "ignored",
        uid: "opaque-uid",
      }),
    ).toEqual({ token: "opaque-token", uid: "opaque-uid" });
    expect(readPasswordResetCredentials({ token: "opaque-token" })).toBeNull();
    expect(
      readPasswordResetCredentials({ token: ["first-token", "second-token"], uid: "opaque-uid" }),
    ).toBeNull();
    expect(readPasswordResetCredentials({ token: "", uid: "opaque-uid" })).toBeNull();
    expect(readPasswordResetCredentials({ unknown: "value" })).toBeNull();
  });
});
