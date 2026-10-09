import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api.js", () => ({ api: { reviewDoc: vi.fn(), saveSection: vi.fn(), makeOutline: vi.fn(), orderSections: vi.fn(), download: vi.fn() } }));
import { api } from "./api.js";
import Write, { insertQuote } from "./Write.jsx";

const SECTION = {
  id: "s1", heading: "What data exists?", sub_question_id: "q1", text: "", words: 0, unverified_quotes: [],
  sources: [{ relation: "same_method", label: "Same method", cards: [{ paper_id: "p1", card_id: "", title: "AUTOMA", quotes: [
    { field: "method", label: "Method", quote: "Our system uses a hypothesis agent and a validation agent.", page: 2, cite: "(Smith & Wei, 2024, p. 2)", complete: true },
    { field: "result", label: "Result", quote: "AUTOMA reaches a precision of 91.4 percent.", page: 3, cite: "(Smith & Wei, 2024, p. 3)", complete: false },
  ] }] }],
};
const DOC = { doc: { id: "d", title: "Literature review" }, style: "apa", words: 0, sections: [SECTION] };

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  api.reviewDoc.mockResolvedValue(DOC);
  api.saveSection.mockResolvedValue({ words: 5, unverified_quotes: [] });
});
afterEach(() => vi.useRealTimers());

describe("insertQuote", () => {
  it("puts the quote on its own line, with the citation and the page", () => {
    expect(insertQuote("", 0, "A quote.", "(Smith, 2024, p. 3)")).toEqual({ text: "> A quote. (Smith, 2024, p. 3)\n", pos: 31 });
    const r = insertQuote("Before. After.", 7, "A quote.", "(S, 2024, p. 3)");
    expect(r.text.startsWith("Before.\n> A quote. (S, 2024, p. 3)\n")).toBe(true);
    expect(r.text.endsWith(" After.")).toBe(true); // the text after the cursor stays
  });
});

describe("Write page", () => {
  it("click Insert: the quote and its citation with the page are in the editor, and the text is saved", async () => {
    const user = userEvent.setup();
    render(<Write notify={vi.fn()} />);
    const area = await screen.findByLabelText("Your text");
    await user.click(screen.getByRole("button", { name: /Insert quote: Our system uses/ }));
    expect(area.value).toBe("> Our system uses a hypothesis agent and a validation agent. (Smith & Wei, 2024, p. 2)\n");
    await user.click(screen.getByRole("button", { name: /Insert quote: AUTOMA reaches/ }));
    expect(area.value.split("\n").filter((l) => l.startsWith("> "))).toHaveLength(2);
    expect(screen.getByText(/check the metadata/)).toBeInTheDocument(); // a citation with missing data says so
    expect(localStorage.getItem("rp-draft-s1")).toContain("p. 3"); // a draft is kept in the browser until the server has it
  });

  it("saves the text after a short pause, and removes the draft", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<Write notify={vi.fn()} />);
    const area = await screen.findByLabelText("Your text");
    await act(async () => {
      const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
      set.call(area, "My own words.");
      area.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(api.saveSection).not.toHaveBeenCalled();
    await act(async () => vi.advanceTimersByTimeAsync(900));
    expect(api.saveSection).toHaveBeenCalledWith("s1", { text: "My own words." });
    expect(localStorage.getItem("rp-draft-s1")).toBeNull();
    expect(await screen.findByText(/Saved/)).toBeInTheDocument();
  });

  it("a draft that was not saved comes back after a reload", async () => {
    localStorage.setItem("rp-draft-s1", "Text from before the reload.");
    render(<Write notify={vi.fn()} />);
    expect((await screen.findByLabelText("Your text")).value).toBe("Text from before the reload.");
  });

  it("warns about a quote that is not in the PDFs", async () => {
    api.reviewDoc.mockResolvedValue({ ...DOC, sections: [{ ...SECTION, unverified_quotes: ["A changed quote (S, 2024, p. 1)"] }] });
    render(<Write notify={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("1 quote is not in your PDFs");
  });

  it("the outline button asks the server, and an empty outline says what to do", async () => {
    api.reviewDoc.mockResolvedValue({ ...DOC, sections: [] });
    api.makeOutline.mockResolvedValue({ ...DOC });
    const user = userEvent.setup();
    render(<Write notify={vi.fn()} />);
    expect(await screen.findByText(/Click “Make the outline”/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Make the outline" }));
    expect(api.makeOutline).toHaveBeenCalled();
  });

  it("the export button saves a file", async () => {
    const user = userEvent.setup();
    api.download.mockResolvedValue();
    render(<Write notify={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: /Export Markdown/ }));
    expect(api.download).toHaveBeenCalledWith("/api/review-doc/export?format=md&style=apa", "literature-review.md");
  });
});
