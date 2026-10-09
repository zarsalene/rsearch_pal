// One store for the state of the whole app (Zustand). A component reads only the part that it needs,
// so a change in one place does not draw the whole app again. The actions live here, next to the state.
import { create } from "zustand";
import { api } from "./api.js";

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

export const useApp = create((set, get) => ({
  tab: "cards",
  papers: [],
  selected: null,
  config: null,
  features: null,
  glossKey: 0, // changes when a word is saved, so the Glossary page reloads
  notice: "",
  libOpen: startLibraryOpen(),

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

  // Called after sign in: load everything that the app needs.
  load: () => {
    get().refresh();
    api.config().then((config) => set({ config })).catch(() => {});
    api.features().then((features) => set({ features })).catch(() => {});
  },
}));

// A feature that is switched off in Settings has no tab. While the list loads, all features show.
export const featureOn = (features, name) => features?.find((f) => f.name === name)?.enabled !== false;
