import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api.js", () => ({ api: { game: vi.fn(), gameSettings: vi.fn(), addReward: vi.fn(), claimReward: vi.fn(), deleteReward: vi.fn() } }));
import { api } from "./api.js";
import GameWatcher from "./GameWatcher.jsx";
import Journey, { LevelCard, StreakCard } from "./Journey.jsx";
import { levelPercent, newThings } from "./game.js";

const GAME = {
  date: "2026-10-09", xp: 80, have: {},
  level: { index: 0, name: "Explorer", floor: 0, names: ["Explorer", "Reader", "Critic", "Connector", "Author", "Doctor"],
    next: { name: "Reader", xp_needed: 20, xp_total: 100, conditions: [{ text: "cards with checked quotes", have: 5, need: 5, available: true }, { text: "Feynman checks passed", have: 1, need: 3, available: true }] } },
  streak: { current: 4, best: 6, tokens_left: 1, today_done: true, weekend_off: true, rest_days: [], message: "Good work today. Rest is part of the work." },
  badges: [{ code: "first_card", name: "First card", how: "Your first card.", earned_at: 1 }],
  badges_missing: [{ code: "streak_7", name: "7-day streak", how: "7 days in a row." }],
  records: { xp: { this_week: 15, last_week: 20, this_month: 35, last_month: 7 }, cards: { this_week: 2, last_week: 1, this_month: 3, last_month: 0 }, focus_minutes: { this_week: 50, last_week: 25, this_month: 75, last_month: 0 } },
  rewards: [{ id: "r1", text: "A dinner out", condition: "level:3", earned_at: null, claimed: false }],
  recent: [{ id: "e1", date: "2026-10-09", label: "A win written", xp: 2 }],
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe("level and streak", () => {
  it("shows the level, the points and what is needed for the next level", () => {
    render(<LevelCard game={GAME} />);
    expect(screen.getByText("Explorer", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText("80 points")).toBeInTheDocument();
    expect(screen.getByText(/20 more points/)).toBeInTheDocument();
    expect(screen.getByText("5 of 5 cards with checked quotes")).toHaveClass("ok");
    expect(screen.getByText("1 of 3 Feynman checks passed")).not.toHaveClass("ok");
    expect(screen.getByRole("progressbar", { name: "Points to Reader" })).toHaveAttribute("aria-valuenow", "80");
  });

  it("says when a part of the app for a level is not built yet", () => {
    const locked = { ...GAME, level: { ...GAME.level, next: { ...GAME.level.next, name: "Critic", conditions: [{ text: "critical reading checks", have: 0, need: 10, available: false }] } } };
    render(<LevelCard game={locked} />);
    expect(screen.getByText(/10 critical reading checks: this part of the app is not built yet/)).toBeInTheDocument();
  });

  it("shows the streak with a kind message and the rest tokens", () => {
    render(<StreakCard streak={GAME.streak} />);
    expect(screen.getByText("Good work today. Rest is part of the work.")).toBeInTheDocument();
    expect(screen.getByText(/Rest tokens left this week: 1 of 2/)).toBeInTheDocument();
  });

  it("the bar for a level goes from the floor to the next level", () => {
    expect(levelPercent(100, 100, 250)).toBe(0);
    expect(levelPercent(175, 100, 250)).toBe(50);
    expect(levelPercent(999, 100, 250)).toBe(100);
    expect(levelPercent(5, 0, null)).toBe(100); // the last level
  });
});

describe("Journey page", () => {
  it("shows badges, records, rewards and where the points came from", async () => {
    api.game.mockResolvedValue(GAME);
    render(<Journey notify={vi.fn()} />);
    expect(await screen.findByText("First card")).toBeInTheDocument();
    expect(screen.getByText("7-day streak")).toBeInTheDocument(); // a badge that is not earned yet, in gray
    expect(screen.getByText(/You compare with your own past only. There is no ranking./)).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /Points 15 20 35 7/ })).toBeInTheDocument();
    expect(screen.getByText("A dinner out")).toBeInTheDocument();
    expect(screen.getByText("A win written")).toBeInTheDocument();
    expect(screen.getByText("+2")).toBeInTheDocument();
  });

  it("an earned reward can be claimed", async () => {
    const user = userEvent.setup();
    api.game.mockResolvedValue({ ...GAME, rewards: [{ id: "r1", text: "A dinner out", condition: "level:3", earned_at: 5, claimed: false }] });
    api.claimReward.mockResolvedValue({});
    render(<Journey notify={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: /You earned it. Claim it/ }));
    expect(api.claimReward).toHaveBeenCalledWith("r1");
  });

  it("the animation switch is saved in the browser", async () => {
    const user = userEvent.setup();
    api.game.mockResolvedValue(GAME);
    render(<Journey notify={vi.fn()} />);
    await user.click(await screen.findByRole("checkbox", { name: /Calm animations/ }));
    expect(localStorage.getItem("rp-anim")).toBe("off");
    expect(document.documentElement).toHaveAttribute("data-anim", "off");
  });
});

describe("a new level or a new badge", () => {
  it("shows nothing at the first visit, then a calm message for each new thing", () => {
    expect(newThings(GAME)).toEqual([]); // the first visit: nothing to compare
    expect(newThings(GAME)).toEqual([]);
    const up = { ...GAME, level: { ...GAME.level, index: 1, name: "Reader" }, badges: [...GAME.badges, { code: "streak_7", name: "7-day streak" }] };
    expect(newThings(up)).toEqual([
      { kind: "level", text: "You are now a Reader." },
      { kind: "badge", text: "New badge: 7-day streak." },
    ]);
    expect(newThings(up)).toEqual([]); // only one time
  });

  it("the watcher shows the message and closes it", async () => {
    const user = userEvent.setup();
    localStorage.setItem("rp-game-seen", JSON.stringify({ level: 0, badges: ["first_card"] }));
    api.game.mockResolvedValue({ ...GAME, level: { ...GAME.level, index: 1, name: "Reader" } });
    render(<GameWatcher tick="today" />);
    expect(await screen.findByText("You are now a Reader.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByText("You are now a Reader.")).not.toBeInTheDocument();
  });

  it("the watcher is quiet when the game is off", async () => {
    api.game.mockRejectedValue(new Error("The feature is switched off."));
    render(<GameWatcher tick="today" />);
    await act(async () => {});
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
