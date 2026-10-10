// One store for the state of the whole app (Zustand). A component reads only the part that it needs,
// so a change in one place does not draw the whole app again. The actions live here, next to the state.
import { create } from "zustand";
import { api } from "./api.js";
import { confetti, getPrefs, play, savePref } from "./juice.js";

export const PHONE = "(max-width: 820px)";
export const isPhone = () => window.matchMedia(PHONE).matches;

// The library can open and close. The choice is saved in this browser.
function startLibraryOpen() {
  try {
    const saved = localStorage.getItem("rp-library");
    // On a phone the library is a drawer. It starts closed, so the card is the first thing you see.
    if (!saved && isPhone()) return false;
    return saved !== "closed";
  } catch {
    return true;
  }
}

let rewardId = 0;

export const useApp = create((set, get) => ({
  tab: "cards",
  papers: [],
  selected: null,
  config: null,
  features: null,
  glossKey: 0, // changes when a word is saved, so the Glossary page reloads
  notice: "",
  libOpen: startLibraryOpen(),
  game: null, // the level, the XP, the streak, the shop ... from the server (see game.py). null until the first answer.
  rewards: [], // short messages about what the student earned
  levelUp: null, // the name of a new level: shows a big card
  battle: null, // the id of the paper in a boss fight
  prefs: getPrefs(), // sound and calm mode

  setTab: (tab) => set({ tab, notice: "" }),
  notify: (notice) => set({ notice }),
  setConfig: (config) => set({ config }),
  setFeatures: (features) => set({ features }),
  bumpGlossary: () => set((s) => ({ glossKey: s.glossKey + 1 })),

  toggleLibrary: () => {
    const open = !get().libOpen;
    try {
      localStorage.setItem("rp-library", open ? "open" : "closed");
    } catch {}
    set({ libOpen: open });
  },
  // Closing is not saved. On a phone the drawer closes by itself, and this must not change the choice of the desktop.
  closeLibrary: () => set({ libOpen: false }),

  refresh: async () => {
    try {
      set({ papers: await api.papers() });
    } catch (e) {
      set({ notice: e.message });
    }
  },
  select: (selected) => set({ selected }),
  openPaper: (id) => {
    set({ selected: id, tab: "cards" });
    // On a phone the library takes the whole width. Close it, so the card is visible.
    if (isPhone()) set({ libOpen: false });
  },

  setPref: (name, on) => {
    savePref(name, on);
    set({ prefs: getPrefs() });
  },

  // ----- the game -----
  reward: (r) => {
    const id = ++rewardId;
    set((s) => ({ rewards: [...s.rewards.slice(-2), { id, ...r }] }));
    setTimeout(() => get().dismissReward(id), r.ms || 4200);
  },
  dismissReward: (id) => set((s) => ({ rewards: s.rewards.filter((r) => r.id !== id) })),
  closeLevelUp: () => set({ levelUp: null }),
  openBattle: (id) => set({ battle: id }),
  closeBattle: () => {
    set({ battle: null });
    get().refreshGame();
  },
  // Show what the student earned. A long list (work from before the game) becomes one message, so the screen stays calm.
  gain: ({ events = [], level_up = null, first = false }) => {
    const { reward } = get();
    if (events.length > 4 || (first && events.length > 1)) {
      const xp = events.reduce((n, e) => n + e.xp, 0);
      reward({ title: `+${xp} XP`, text: first ? "Welcome! Your earlier work gave you XP." : "Your work gave you XP.", tone: "xp" });
      play("spark");
    } else {
      for (const e of events) {
        const eureka = e.action === "eureka";
        reward({ title: `+${e.xp} XP`, text: e.label, tone: eureka ? "eureka" : e.action === "comeback" ? "kind" : "xp" });
        play(eureka ? "level" : "spark");
        if (eureka) confetti("small");
      }
    }
    if (level_up) {
      set({ levelUp: level_up });
      play("level");
      confetti("big");
    }
  },
  // Ask the server for the game state. The server also pays the XP that real work has earned (a new card, a word, a link), and tells it in "new".
  refreshGame: async () => {
    if (!featureOn(get().features, "game")) return null;
    try {
      const game = await api.game();
      const first = get().game === null;
      set({ game });
      get().gain({ events: game.new, level_up: game.level_up, first });
      return game;
    } catch {
      return null; // the game must never stop the app
    }
  },

  // Called after sign in: load everything that the app needs.
  load: () => {
    get().refresh();
    get().refreshGame();
    api.config().then((config) => set({ config })).catch(() => {});
    api.features().then((features) => set({ features })).catch(() => {});
  },
}));

// A feature that is switched off in Settings has no tab. While the list loads, all features show.
export const featureOn = (features, name) => features?.find((f) => f.name === name)?.enabled !== false;
