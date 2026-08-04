import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReadinessStatus } from "@/components/readiness-status";
import { checkReadiness } from "@/lib/api/readiness";

vi.mock("@/lib/api/readiness", () => ({
  checkReadiness: vi.fn(),
}));

const checkReadinessMock = vi.mocked(checkReadiness);

describe("readiness status", () => {
  afterEach(cleanup);

  beforeEach(() => {
    checkReadinessMock.mockReset();
  });

  it("announces the ready state", async () => {
    checkReadinessMock.mockResolvedValue("ready");

    render(
      <dl>
        <ReadinessStatus />
      </dl>,
    );

    expect(await screen.findByRole("status")).toHaveTextContent("Backend and database ready");
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });

  it("offers a disabled retry while recovering from an unavailable database", async () => {
    let finishRetry: ((value: "ready") => void) | undefined;
    checkReadinessMock.mockResolvedValueOnce("database-unavailable").mockReturnValueOnce(
      new Promise((resolve) => {
        finishRetry = resolve;
      }),
    );

    render(
      <dl>
        <ReadinessStatus />
      </dl>,
    );

    expect(await screen.findByRole("status")).toHaveTextContent("Database unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(screen.getByRole("status")).toHaveTextContent("Retrying local services");
    expect(screen.getByRole("button", { name: "Trying again…" })).toBeDisabled();

    await act(async () => finishRetry?.("ready"));

    expect(await screen.findByRole("status")).toHaveTextContent("Backend and database ready");
  });
});
