import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ErrorPage from "@/app/error";

describe("error state", () => {
  it("shows a generic message and lets the learner retry", () => {
    const reset = vi.fn();

    render(<ErrorPage error={new Error("private detail")} reset={reset} />);

    expect(screen.getByRole("alert")).not.toBeEmptyDOMElement();
    expect(screen.getByRole("alert")).not.toHaveTextContent("private detail");

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(reset).toHaveBeenCalledOnce();
  });
});
