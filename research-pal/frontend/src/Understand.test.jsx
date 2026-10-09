import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("./api.js", () => ({ api: { openPdf: vi.fn().mockResolvedValue() } }));
import { ClaimText, ExplainResult } from "./Understand.jsx";

const CLAIMS = [
  { id: 1, text: "The system has two agents.", mark: "correct", label: "Correct", comment: "Good. You named the agents.", quote: "Our system uses a hypothesis agent and a validation agent.", page: 2, verified: true, source: "ai" },
  { id: 2, text: "It is fast on all data.", mark: "partly", label: "Partly correct", comment: "The paper tests one dataset.", quote: "We test only on one dataset.", page: 3, verified: true, source: "ai" },
  { id: 3, text: "The recall is 95.0 percent.", mark: "wrong", label: "Wrong", comment: "The number 95.0 is not in the paper.", quote: "", page: 0, verified: false, source: "server" },
  { id: 4, text: "It also cooks pasta.", mark: "not_in_paper", label: "Not in the paper", comment: "The AI did not find this in the paper.", quote: "", page: 0, verified: false, source: "ai" },
  { id: 5, text: "It is a good idea.", mark: "cannot_check", label: "Cannot check", comment: "The server could not find the quote of the AI in the PDF.", quote: "", page: 0, verified: false, source: "ai" },
];
const RESULT = {
  id: "r1", claims: CLAIMS, score: 55, message: "Good start. 1 point is missing. 1 claim needs a second look.",
  counts: { correct: 1, partly: 1, wrong: 1, not_in_paper: 1, cannot_check: 1 },
  missing: [{ field: "problem", label: "Problem", answer: "Analysts spend many hours on manual log review.", page: 1 }],
};

describe("Feynman result", () => {
  it("shows each mark in its own color", () => {
    render(<ClaimText claims={CLAIMS} activeId={null} onPick={() => {}} />);
    expect(screen.getByRole("button", { name: /\(Correct\)$/ })).toHaveClass("mark-correct"); // green
    expect(screen.getByRole("button", { name: /\(Partly correct\)$/ })).toHaveClass("mark-partly"); // orange
    expect(screen.getByRole("button", { name: /\(Wrong\)$/ })).toHaveClass("mark-wrong"); // red
    expect(screen.getByRole("button", { name: /\(Not in the paper\)$/ })).toHaveClass("mark-not_in_paper");
    expect(screen.getByRole("button", { name: /\(Cannot check\)$/ })).toHaveClass("mark-cannot_check");
  });

  it("shows the score, the kind message and the missing points", () => {
    render(<ExplainResult result={RESULT} paperId="p1" notify={() => {}} />);
    expect(screen.getByLabelText("Score 55 of 100")).toBeInTheDocument();
    expect(screen.getByText(/Good start. 1 point is missing/)).toBeInTheDocument();
    expect(screen.getByText("Points that you did not mention")).toBeInTheDocument();
    expect(screen.getByText(/Analysts spend many hours/)).toBeInTheDocument();
  });

  it("a click on a sentence shows the quote and the page, or the reason", async () => {
    const user = userEvent.setup();
    render(<ExplainResult result={RESULT} paperId="p1" notify={() => {}} />);
    await user.click(screen.getByText("The system has two agents."));
    const detail = screen.getByRole("region", { name: "Proof for the selected claim" });
    expect(within(detail).getByText(/hypothesis agent and a validation agent/)).toBeInTheDocument();
    expect(within(detail).getByRole("button", { name: "p. 2" })).toBeInTheDocument();

    await user.click(screen.getByText("The recall is 95.0 percent."));
    const wrong = screen.getByRole("region", { name: "Proof for the selected claim" });
    expect(within(wrong).getByText("The number 95.0 is not in the paper.")).toBeInTheDocument();
    expect(within(wrong).getByText(/server checked the numbers/)).toBeInTheDocument();
    expect(within(wrong).queryByRole("button")).not.toBeInTheDocument(); // no quote, no page chip

    await user.click(screen.getByText("It is a good idea."));
    expect(screen.getByText(/shows no mark here/)).toBeInTheDocument();
  });
});
