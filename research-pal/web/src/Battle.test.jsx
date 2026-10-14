import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api.js", () => ({ api: { startBattle: vi.fn(), answerBattle: vi.fn(), openPdf: vi.fn(async () => {}), game: vi.fn() } }));
import { api } from "./api.js";
import Battle from "./Battle.jsx";

const OPTIONS = ["A hypothesis agent and a validation agent", "A database", "A camera", "A radio"];
const QUOTE = "Our system uses a hypothesis agent and a validation agent.";
const fight = (over = {}) => ({
  id: "b1", paper_id: "p1", title: "AUTOMA: Multi-agent threat hunting", status: "active", hp: 100, hp_max: 100, hearts: 3, hearts_max: 3, combo: 0, best_combo: 0,
  index: 0, total: 3, xp: 0, question: { n: 0, text: "What does the system use?", options: OPTIONS, field: "Method" }, history: [], result: null, ...over,
});
const entry = (over = {}) => ({ n: 0, text: "What does the system use?", options: OPTIONS, chosen: 0, answer: 0, correct: true, field: "Method", proof: { quote: QUOTE, page: 2, verified: true }, ...over });
const answered = (over = {}) => ({
  correct: true, answer: 0, damage: 34, crit: false, xp: 5, extra: [], level_up: null, total_xp: 5, proof: { quote: QUOTE, page: 2, verified: true },
  battle: fight({ index: 1, hp: 66, combo: 1, question: { n: 1, text: "Next one?", options: OPTIONS, field: "Result" }, history: [entry()] }),
  ...over,
});

beforeEach(() => vi.clearAllMocks());

describe("Battle", () => {
  it("shows the boss, the hearts and the first question", async () => {
    api.startBattle.mockResolvedValue(fight());
    render(<Battle paperId="p1" onClose={() => {}} />);
    expect(screen.getByText(/The boss is waking up/)).toBeInTheDocument();
    expect(await screen.findByText("What does the system use?")).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: /Boss fight: AUTOMA/ })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "3 of 3 hearts left" })).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Boss health" })).toHaveAttribute("aria-valuenow", "100");
    expect(screen.getByRole("group", { name: "Answers" }).querySelectorAll("button")).toHaveLength(4);
    expect(api.startBattle).toHaveBeenCalledWith("p1");
  });

  it("sends the number of the question and the choice. The server decides if it is right.", async () => {
    api.startBattle.mockResolvedValue(fight());
    api.answerBattle.mockResolvedValue(answered());
    render(<Battle paperId="p1" onClose={() => {}} />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /A hypothesis agent and a validation agent/ }));
    expect(api.answerBattle).toHaveBeenCalledWith("b1", 0, 0);
    expect(await screen.findByText(/Right! −34 HP/)).toBeInTheDocument();
    expect(screen.getByText("+5 XP")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Boss health" })).toHaveAttribute("aria-valuenow", "66");
    // the proof: the quote and its page
    expect(screen.getByText(QUOTE)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Proof · p. 2/ }));
    expect(api.openPdf).toHaveBeenCalledWith("p1", 2);
    // the next question
    await user.click(screen.getByRole("button", { name: /Next question/ }));
    expect(await screen.findByText("Next one?")).toBeInTheDocument();
  });

  it("is kind to a wrong answer: a heart, the right answer and the proof", async () => {
    api.startBattle.mockResolvedValue(fight());
    const r = answered({ correct: false, damage: 0, xp: 0 });
    r.battle = { ...r.battle, hearts: 2, hp: 100, history: [entry({ chosen: 2, correct: false })] };
    api.answerBattle.mockResolvedValue(r);
    render(<Battle paperId="p1" onClose={() => {}} />);
    await userEvent.setup().click(await screen.findByRole("button", { name: /A camera/ }));
    expect(await screen.findByText(/Not this time. You lose a heart./)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "2 of 3 hearts left" })).toBeInTheDocument();
    expect(screen.getByText(QUOTE)).toBeInTheDocument();
    expect(screen.queryByText("+0 XP")).not.toBeInTheDocument();
  });

  it("shows a win with the result, and starts another fight", async () => {
    api.startBattle.mockResolvedValueOnce(fight());
    const win = answered({ xp: 53 });
    win.battle = { ...win.battle, status: "won", hp: 0, question: null, xp: 71, best_combo: 3, history: [0, 1, 2].map((n) => entry({ n })),
      result: { won: true, flawless: true, text: "You won with all your hearts. Great work.", xp: 71 } };
    api.answerBattle.mockResolvedValue(win);
    render(<Battle paperId="p1" onClose={() => {}} />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /A hypothesis agent and a validation agent/ }));
    await user.click(await screen.findByRole("button", { name: /See the result/ }));
    expect(await screen.findByRole("heading", { name: "Flawless victory!" })).toBeInTheDocument();
    expect(screen.getByText("3/3")).toBeInTheDocument();
    expect(screen.getByText("+71")).toBeInTheDocument();
    api.startBattle.mockResolvedValueOnce(fight({ id: "b2" }));
    await user.click(screen.getByRole("button", { name: /Fight again/ }));
    await waitFor(() => expect(api.startBattle).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("What does the system use?")).toBeInTheDocument();
  });

  it("shows a lost fight without blame", async () => {
    api.startBattle.mockResolvedValue(fight());
    const lost = answered({ correct: false, damage: 0, xp: 0 });
    lost.battle = { ...lost.battle, status: "lost", hearts: 0, question: null, history: [entry({ correct: false, chosen: 3 })],
      result: { won: false, flawless: false, text: "The boss wins this round. Nothing is lost. Read the card again, then try again.", xp: 0 } };
    api.answerBattle.mockResolvedValue(lost);
    render(<Battle paperId="p1" onClose={() => {}} />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /A radio/ }));
    await user.click(await screen.findByRole("button", { name: /See the result/ }));
    expect((await screen.findAllByText(/Nothing is lost/)).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /Fight again/ })).toBeInTheDocument();
  });

  it("tells the student when the fight cannot start", async () => {
    api.startBattle.mockRejectedValue(new Error("The card has too few checked claims for a fight."));
    const onClose = vi.fn();
    render(<Battle paperId="p1" onClose={onClose} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("too few checked claims");
    await userEvent.setup().click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("answers with the keys 1 to 4 and leaves with Escape", async () => {
    api.startBattle.mockResolvedValue(fight());
    api.answerBattle.mockResolvedValue(answered());
    const onClose = vi.fn();
    render(<Battle paperId="p1" onClose={onClose} />);
    await screen.findByText("What does the system use?");
    const user = userEvent.setup();
    await user.keyboard("2");
    expect(api.answerBattle).toHaveBeenCalledWith("b1", 0, 1);
    await screen.findByText(/Right!/);
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });
});
