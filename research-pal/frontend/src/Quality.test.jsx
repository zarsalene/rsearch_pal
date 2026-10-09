import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api.js", () => ({ api: { getCritique: vi.fn(), runCritique: vi.fn(), editCritique: vi.fn(), subQuestions: vi.fn(), getGaps: vi.fn(), runGaps: vi.fn(), setGapStatus: vi.fn(), useGap: vi.fn() } }));
import { api } from "./api.js";
import Gaps from "./Gaps.jsx";
import Quality from "./Quality.jsx";

const ITEM = { key: "method", question: "Does the method fit the question?", answer: "yes", comment: "The method fits.", quote: "Our system uses a hypothesis agent", page: 2, verified: true, edited: false };
const UNCLEAR = { key: "bias", question: "Is the risk of bias low?", answer: "unclear", comment: "", quote: "", page: 0, verified: false, edited: false };

beforeEach(() => vi.clearAllMocks());

describe("Quality check", () => {
  it("shows the AI opinion label, the checked quote, and Unclear without a quote", async () => {
    api.getCritique.mockResolvedValue({ items: [ITEM, UNCLEAR], confirmed: false });
    render(<Quality paperId="p1" notify={() => {}} />);
    expect(await screen.findByText("Does the method fit the question?")).toBeInTheDocument();
    expect(screen.getAllByText(/AI opinion/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Our system uses a hypothesis agent/)).toBeInTheDocument();
    expect(screen.getByText(/No checked quote/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check again" })).toBeInTheDocument();
  });
  it("runs the check when there is none", async () => {
    api.getCritique.mockResolvedValue({ items: [], confirmed: false });
    api.runCritique.mockResolvedValue({ items: [ITEM], confirmed: false });
    render(<Quality paperId="p1" notify={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: "Run the quality check" }));
    expect(await screen.findByText("Does the method fit the question?")).toBeInTheDocument();
  });
  it("changes an answer and confirms the check", async () => {
    api.getCritique.mockResolvedValue({ items: [ITEM], confirmed: false });
    api.editCritique.mockResolvedValue({ items: [{ ...ITEM, answer: "no", edited: true }], confirmed: false });
    render(<Quality paperId="p1" notify={() => {}} />);
    await userEvent.selectOptions(await screen.findByLabelText(/Answer: Does the method/), "no");
    expect(api.editCritique).toHaveBeenCalledWith("p1", { method: { answer: "no" } }, false);
    expect(await screen.findByText("Changed by you.")).toBeInTheDocument();
    api.editCritique.mockResolvedValue({ items: [{ ...ITEM, answer: "no", edited: true }], confirmed: true });
    await userEvent.click(screen.getByRole("button", { name: "Confirm this check" }));
    expect(await screen.findByText("You confirmed this check.")).toBeInTheDocument();
  });
});

describe("Gaps", () => {
  const RUN = {
    run_id: "r1",
    agree: [{ point: "Both papers use agents.", evidence: [{ quote: "uses a hypothesis agent", page: 2, title: "Paper A" }, { quote: "uses two agents", page: 1, title: "Paper B" }] }],
    disagree: [],
    gap: [{ id: "g1", point: "Nobody tests on real networks.", reason: "Both use one dataset.", status: "new", label: "AI opinion" }],
  };
  it("shows three columns, labels the gap as an AI opinion, and lets the student decide", async () => {
    api.subQuestions.mockResolvedValue([{ id: "s1", text: "What data exists?" }]);
    api.getGaps.mockResolvedValue(RUN);
    api.setGapStatus.mockResolvedValue({});
    api.useGap.mockResolvedValue({});
    const notify = vi.fn();
    render(<Gaps notify={notify} />);
    expect(await screen.findByText("Both papers use agents.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Agree" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Disagree" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Gap" })).toBeInTheDocument();
    expect(screen.getByText(/Paper A, page 2/)).toBeInTheDocument();
    expect(screen.getAllByText(/AI opinion/).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("button", { name: /Confirm the gap/ }));
    expect(api.setGapStatus).toHaveBeenCalledWith("g1", "confirmed");
    await userEvent.click(screen.getByRole("button", { name: /Use this gap/ }));
    expect(api.useGap).toHaveBeenCalledWith("g1");
    await waitFor(() => expect(notify).toHaveBeenCalledWith(expect.stringMatching(/section in your outline/)));
  });
  it("runs the finder and shows an empty state before", async () => {
    api.subQuestions.mockResolvedValue([{ id: "s1", text: "What data exists?" }]);
    api.getGaps.mockResolvedValue({ run_id: null, agree: [], disagree: [], gap: [] });
    api.runGaps.mockResolvedValue(RUN);
    render(<Gaps notify={() => {}} />);
    expect(await screen.findByText(/No comparison yet/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Find gaps" }));
    expect(api.runGaps).toHaveBeenCalledWith({ sub_question_id: "s1" });
    expect(await screen.findByText("Nobody tests on real networks.")).toBeInTheDocument();
  });
});
