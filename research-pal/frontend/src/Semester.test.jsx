import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api.js", () => ({ api: { sim: vi.fn(), simStart: vi.fn(), simAct: vi.fn(), simChoose: vi.fn(), simEndWeek: vi.fn(), simBoost: vi.fn(), game: vi.fn() } }));
import { api } from "./api.js";
import { useApp } from "./store.js";
import Semester from "./Semester.jsx";

const ACTIONS = [
  ["read", "Read papers", 1, -8], ["study", "Study one paper", 1, -6], ["experiment", "Run a test", 2, -15], ["write", "Write", 2, -12],
  ["meet", "Meet your supervisor", 1, -3], ["network", "Talk to researchers", 1, -6], ["rest", "Rest", 1, 22],
].map(([id, label, ap, energy]) => ({ id, label, ap, energy, text: label + " text", enabled: true, why: "" }));
const run = (over = {}) => ({
  id: "s1", status: "active", week: 1, weeks: 12, ap: 5, ap_max: 5, energy: 70, morale: 70, trust: 50, knowledge: 12,
  chapters: { review: 0, method: 0, experiments: 0, writing: 0 }, chapter_names: { review: "Literature review", method: "Method", experiments: "Tests", writing: "Writing" }, progress: 0,
  milestones: [{ week: 4, label: "Literature review draft", done: false, ok: null }, { week: 8, label: "Method and tests check", done: false, ok: null }, { week: 12, label: "Final report", done: false, ok: null }],
  event: null, coming: null, actions: ACTIONS, papers: [{ id: "p1", title: "AUTOMA", rank: 1, rank_name: "read", prepared: false }], boosts: {}, armed: false, coffee_used: false,
  real: { knowledge: 12, mastered: 0, explained: 0, read: 1, links: 0 }, log: [], report: null, ...over,
});
const records = { runs: 0, best: 0, best_grade: "", last: null };

beforeEach(() => {
  vi.clearAllMocks();
  useApp.setState({ game: { stats: { papers: 1, mastered: 0 }, outfit: {}, level: { index: 0 } } });
});

describe("Semester Simulator", () => {
  it("starts with an explanation, and says that the game gives no XP", async () => {
    api.sim.mockResolvedValue({ run: null, records });
    render(<Semester notify={() => {}} onBack={() => {}} />);
    expect(await screen.findByRole("heading", { name: "Plan 12 weeks of research" })).toBeInTheDocument();
    expect(screen.getByText(/It gives no XP/)).toBeInTheDocument();
    expect(screen.getByText(/It uses your real work/)).toBeInTheDocument();
  });

  it("starts a semester, and spends action points with the choices of the student", async () => {
    api.sim.mockResolvedValue({ run: null, records });
    api.simStart.mockResolvedValue(run());
    api.simAct.mockResolvedValue({ say: "You read papers. Literature review +6.", run: run({ ap: 4, energy: 62, chapters: { review: 6, method: 0, experiments: 0, writing: 0 } }), records });
    render(<Semester notify={() => {}} onBack={() => {}} />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Start a semester/ }));
    expect(await screen.findByText("5 action points")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Energy" })).toHaveAttribute("aria-valuenow", "70");
    await user.click(screen.getByRole("button", { name: /^Read papers/ }));
    expect(api.simAct).toHaveBeenCalledWith("s1", "read", "");
    expect(await screen.findByText("You read papers. Literature review +6.")).toBeInTheDocument();
    expect(screen.getByText("4 action points")).toBeInTheDocument();
  });

  it("asks which real paper to study", async () => {
    api.sim.mockResolvedValue({ run: run(), records });
    api.simAct.mockResolvedValue({ say: "You study.", run: run({ ap: 4 }), records });
    render(<Semester notify={() => {}} onBack={() => {}} />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /^Study one paper/ }));
    await user.click(screen.getByRole("button", { name: /AUTOMA/ }));
    expect(api.simAct).toHaveBeenCalledWith("s1", "study", "p1");
  });

  it("blocks the actions during an event, and shows the odds of a real paper", async () => {
    const ev = { id: "reviewer", title: "Reviewer 2 writes to you", text: "The reviewer asks about AUTOMA. In the app, this paper is read.", paper: { id: "p1" },
      choices: [{ id: "answer", label: "Answer from your notes", risk: "risky", hint: "Fair odds" }, { id: "ask", label: "Ask your supervisor for help", risk: "safe", hint: "Trust -3. A small gain." }] };
    api.sim.mockResolvedValue({ run: run({ event: ev }), records });
    api.simChoose.mockResolvedValue({ say: "You answer well.", run: run({ week: 2 }), records });
    render(<Semester notify={() => {}} onBack={() => {}} />);
    expect(await screen.findByRole("heading", { name: "Reviewer 2 writes to you" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Read papers/ })).not.toBeInTheDocument();
    expect(screen.getByText(/Risk · Fair odds/)).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: /Answer from your notes/ }));
    expect(api.simChoose).toHaveBeenCalledWith("s1", "answer");
  });

  it("ends the week", async () => {
    api.sim.mockResolvedValue({ run: run({ ap: 0 }), records });
    api.simEndWeek.mockResolvedValue({ say: "", run: run({ week: 2 }), records });
    render(<Semester notify={() => {}} onBack={() => {}} />);
    await userEvent.setup().click(await screen.findByRole("button", { name: /End the week/ }));
    expect(api.simEndWeek).toHaveBeenCalledWith("s1");
  });

  it("shows a disabled action with its reason", async () => {
    const acts = ACTIONS.map((a) => (a.id === "write" ? { ...a, enabled: false, why: "Not enough action points." } : a));
    api.sim.mockResolvedValue({ run: run({ actions: acts, ap: 1 }), records });
    render(<Semester notify={() => {}} onBack={() => {}} />);
    expect(await screen.findByRole("button", { name: /^Write\. 2 action points\. Not enough action points\./ })).toBeDisabled();
  });

  it("shows the report with the real papers that the student must learn, and a way to their boss", async () => {
    const report = { progress: 62, grade: "B", burnout: false, weeks_done: 12, chapters: { review: 70, method: 50, experiments: 60, writing: 65 }, tip: "Plan more weeks for tests. Read first, then test.", weakest: "method",
      weak_spots: [{ id: "p3", title: "Paper three", rank: 0 }], next_steps: ["Fight the boss of Paper three in the real app. A reviewer asked about it."], real: { knowledge: 23, mastered: 1, explained: 0, read: 1, links: 1 },
      text: "A good semester. You are on the way." };
    api.sim.mockResolvedValue({ run: run({ status: "done", report, progress: 62 }), records: { runs: 1, best: 62, best_grade: "B", last: { progress: 62, grade: "B" } } });
    const open = vi.fn();
    useApp.setState({ openBattle: open });
    render(<Semester notify={() => {}} onBack={() => {}} />);
    expect(await screen.findByText("Your thesis is 62% ready")).toBeInTheDocument();
    expect(screen.getByText("B")).toBeInTheDocument();
    expect(screen.getByText(/Your real work gave you 13 knowledge at the start/)).toBeInTheDocument();
    expect(screen.getByText("New personal best")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: /Fight: Paper three/ }));
    expect(open).toHaveBeenCalledWith("p3");
  });

  it("is kind after a burnout", async () => {
    const report = { progress: 30, grade: "D", burnout: true, weeks_done: 7, chapters: { review: 30, method: 20, experiments: 30, writing: 30 }, tip: "Read more in the first weeks.", weakest: "method", weak_spots: [], next_steps: [],
      real: { knowledge: 10, mastered: 0, explained: 0, read: 0, links: 0 }, text: "Burnout ended the semester early. Your progress is safe. Rest, then try again." };
    api.sim.mockResolvedValue({ run: run({ status: "burnout", report }), records: { runs: 1, best: 30, best_grade: "D", last: null } });
    render(<Semester notify={() => {}} onBack={() => {}} />);
    expect(await screen.findByText("Burnout in week 7")).toBeInTheDocument();
    expect(screen.getByText(/Your progress is safe/)).toBeInTheDocument();
  });
});
