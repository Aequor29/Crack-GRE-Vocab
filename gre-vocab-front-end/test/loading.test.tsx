import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Loading from "@/app/loading";

describe("loading state", () => {
  it("announces that the application is loading", () => {
    render(<Loading />);

    expect(screen.getByRole("status", { name: "Loading application" })).toHaveTextContent(
      "Loading Crack GRE Vocab.",
    );
  });
});
