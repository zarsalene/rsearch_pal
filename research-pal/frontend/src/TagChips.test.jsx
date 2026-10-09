import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import TagChips, { sqLabel } from "./TagChips.jsx";

const SQS = [
  { id: "a", text: "What data exists?" },
  { id: "b", text: "Which method works?" },
  { id: "c", text: "How do we measure it?" },
];

describe("TagChips", () => {
  it("shows one chip for each sub-question, and marks the chosen ones", () => {
    render(<TagChips subQuestions={SQS} selected={["b"]} onChange={() => {}} />);
    expect(screen.getAllByRole("button")).toHaveLength(3);
    expect(screen.getByRole("button", { name: "SQ2" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "SQ1" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "SQ1" })).toHaveAttribute("title", "What data exists?");
  });

  it("adds and removes a tag", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<TagChips subQuestions={SQS} selected={["b"]} onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: "SQ3" }));
    expect(onChange).toHaveBeenLastCalledWith(["b", "c"]);
    await user.click(screen.getByRole("button", { name: "SQ2" }));
    expect(onChange).toHaveBeenLastCalledWith([]);
  });

  it("shows nothing when there is no sub-question", () => {
    const { container } = render(<TagChips subQuestions={[]} onChange={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("names a sub-question by its place", () => {
    expect(sqLabel(SQS, "c")).toBe("SQ3");
    expect(sqLabel(SQS, "zzz")).toBe("");
  });
});
