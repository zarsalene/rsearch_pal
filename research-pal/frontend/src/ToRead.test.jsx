import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api.js", () => ({ api: { toRead: vi.fn(), setToRead: vi.fn(), readToRead: vi.fn(), uploadToRead: vi.fn(), refreshSuggestions: vi.fn() } }));
import { api } from "./api.js";
import ToRead from "./ToRead.jsx";

const ITEMS = [
  { id: "a", title: "Agents read logs", authors: ["Doe, John"], year: "2022", venue: "Log Journal", abstract: "Agents read network logs.", score: 72, reason: "Fits SQ2: 'agents, logs'" },
  { id: "b", title: "Cooking pasta", authors: [], year: "2020", venue: "", abstract: "", score: 8, reason: "No clear fit with your question." },
];

beforeEach(() => {
  vi.clearAllMocks();
  api.toRead.mockResolvedValue(ITEMS);
});

describe("To read", () => {
  it("shows the score and the reason of each item, best first", async () => {
    render(<ToRead notify={() => {}} />);
    expect(await screen.findByText("Agents read logs")).toBeInTheDocument();
    expect(screen.getByLabelText("Fit score 72 of 100")).toBeInTheDocument();
    expect(screen.getByText(/Fits SQ2/)).toBeInTheDocument();
    expect(screen.getByText("No clear fit with your question.")).toBeInTheDocument();
  });
  it("says what to do when the list is empty", async () => {
    api.toRead.mockResolvedValue([]);
    render(<ToRead notify={() => {}} />);
    expect(await screen.findByText(/The list is empty/)).toBeInTheDocument();
  });
  it("reads now, and tells the student when there is no free PDF", async () => {
    api.readToRead.mockRejectedValueOnce(new Error("No free PDF was found. Upload the PDF yourself."));
    const notify = vi.fn();
    const onChanged = vi.fn();
    render(<ToRead notify={notify} onChanged={onChanged} />);
    await userEvent.click((await screen.findAllByRole("button", { name: "Read now" }))[0]);
    await waitFor(() => expect(notify).toHaveBeenCalledWith("No free PDF was found. Upload the PDF yourself."));
    expect(onChanged).not.toHaveBeenCalled();
    api.readToRead.mockResolvedValueOnce({ id: "p1", status: "queued" });
    await userEvent.click(screen.getAllByRole("button", { name: "Read now" })[0]);
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
  });
  it("marks an item as not useful and reloads the list", async () => {
    api.setToRead.mockResolvedValue({});
    render(<ToRead notify={() => {}} />);
    await userEvent.click((await screen.findAllByRole("button", { name: "Not useful" }))[1]);
    expect(api.setToRead).toHaveBeenCalledWith("b", "not_useful");
    await waitFor(() => expect(api.toRead).toHaveBeenCalledTimes(2));
  });
  it("tags a suggestion and looks for new suggestions on request", async () => {
    api.toRead.mockResolvedValue([{ ...ITEMS[0], source: "suggested", reason: "Cited by 4 of your papers" }]);
    api.refreshSuggestions.mockResolvedValue({ added: 2, message: "2 new suggestions in your To read list." });
    const notify = vi.fn();
    render(<ToRead notify={notify} suggestOn />);
    expect(await screen.findByText("Suggested")).toBeInTheDocument();
    expect(screen.getByText("Cited by 4 of your papers")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Suggest papers now" }));
    await waitFor(() => expect(notify).toHaveBeenCalledWith("2 new suggestions in your To read list."));
  });
});
