import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import StudyPage from "@/app/study/page";

vi.mock("@/components/study/study-session", () => ({
  StudySession: () => <p>Study session content</p>,
}));

describe("study page hierarchy", () => {
  it("keeps the page title semantic without distracting from the active card", () => {
    render(<StudyPage />);

    expect(screen.queryByText("Durable recall")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "One word at a time." })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Study vocabulary" })).toHaveClass("sr-only");
    expect(screen.getByText("Study session content")).toBeInTheDocument();
  });
});
