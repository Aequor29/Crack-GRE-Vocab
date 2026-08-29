import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import StudyPage from "@/app/study/page";

vi.mock("@/components/study/study-session", () => ({
  StudySession: () => <p>Study session content</p>,
}));

describe("study page hierarchy", () => {
  it("provides a semantic page title for the study experience", () => {
    render(<StudyPage />);

    expect(screen.getByRole("heading", { name: "Study vocabulary" })).toHaveClass("sr-only");
    expect(screen.getByText("Study session content")).toBeInTheDocument();
  });
});
