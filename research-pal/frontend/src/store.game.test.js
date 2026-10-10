import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api.js", () => ({ api: { game: vi.fn(), papers: vi.fn(async () => []), config: vi.fn(async () => ({})), features: vi.fn(async () => []) } }));
vi.mock("./juice.js", () => ({ play: vi.fn(), confetti: vi.fn(), getPrefs: () => ({ sound: true, calm: false }), savePref: vi.fn() }));

describe("the game in the store", () => {
  let useApp, api, play, confetti;
  beforeEach(async () => {
    vi.useFakeTimers();
    vi.resetModules();
    vi.clearAllMocks();
    ({ api } = await import("./api.js"));
    api.game.mockReset();
    ({ play, confetti } = await import("./juice.js"));
    ({ useApp } = await import("./store.js"));
  });

  const ev = (action, xp, label = action) => ({ action, xp, label, ref_id: "x" });

  it("shows one message for each new event", () => {
    useApp.getState().gain({ events: [ev("card_ready", 10, "Card ready"), ev("word_saved", 3, "Word saved")] });
    expect(useApp.getState().rewards.map((r) => r.title)).toEqual(["+10 XP", "+3 XP"]);
    expect(play).toHaveBeenCalledWith("spark");
  });

  it("makes one calm message from a long list (work from before the game)", () => {
    useApp.getState().gain({ events: Array.from({ length: 9 }, () => ev("card_ready", 10)), first: true });
    const r = useApp.getState().rewards;
    expect(r).toHaveLength(1);
    expect(r[0]).toMatchObject({ title: "+90 XP", text: "Welcome! Your earlier work gave you XP." });
  });

  it("celebrates a lucky find and a level up", () => {
    useApp.getState().gain({ events: [ev("eureka", 15, "Eureka! A lucky find")], level_up: "Reader" });
    expect(useApp.getState().rewards[0].tone).toBe("eureka");
    expect(useApp.getState().levelUp).toBe("Reader");
    expect(confetti).toHaveBeenCalledWith("big");
    useApp.getState().closeLevelUp();
    expect(useApp.getState().levelUp).toBeNull();
  });

  it("is kind to a student who comes back", () => {
    useApp.getState().gain({ events: [ev("comeback", 15, "Welcome back")] });
    expect(useApp.getState().rewards[0].tone).toBe("kind");
  });

  it("a message goes away by itself, and the list stays short", () => {
    const { reward } = useApp.getState();
    for (let i = 0; i < 6; i++) reward({ title: "t" + i, text: "", tone: "xp" });
    expect(useApp.getState().rewards).toHaveLength(3);
    vi.advanceTimersByTime(5000);
    expect(useApp.getState().rewards).toHaveLength(0);
  });

  it("loads the game and tells what is new", async () => {
    api.game.mockResolvedValue({ xp: 10, new: [ev("card_ready", 10)], level_up: null });
    const g = await useApp.getState().refreshGame();
    expect(g.xp).toBe(10);
    expect(useApp.getState().game.xp).toBe(10);
    expect(useApp.getState().rewards).toHaveLength(1);
  });

  it("never stops the app when the game fails", async () => {
    api.game.mockRejectedValue(new Error("down"));
    expect(await useApp.getState().refreshGame()).toBeNull();
    expect(useApp.getState().game).toBeNull();
  });

  it("does not call the server when the game feature is off", async () => {
    useApp.setState({ features: [{ name: "game", enabled: false }] });
    expect(await useApp.getState().refreshGame()).toBeNull();
    expect(api.game).not.toHaveBeenCalled();
  });

  it("opens and closes a boss fight, and looks at the game again", () => {
    api.game.mockResolvedValue({ xp: 0, new: [], level_up: null });
    useApp.getState().openBattle("p1");
    expect(useApp.getState().battle).toBe("p1");
    useApp.getState().closeBattle();
    expect(useApp.getState().battle).toBeNull();
    expect(api.game).toHaveBeenCalled();
  });
});
