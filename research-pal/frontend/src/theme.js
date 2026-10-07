// Light, Dark or System. The choice is saved in this browser. index.html applies it before the first paint.
const KEY = "rp-theme";
const COLORS = { light: "#FAFAF9", dark: "#000000" };

export function getMode() {
  try {
    const m = localStorage.getItem(KEY);
    return m === "light" || m === "dark" ? m : "system";
  } catch {
    return "system";
  }
}

function systemIsDark() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function applyMode(mode) {
  const theme = mode === "dark" || (mode === "system" && systemIsDark()) ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", theme);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", COLORS[theme]);
}

export function setMode(mode) {
  try {
    if (mode === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, mode);
  } catch {
    /* private mode: the choice lasts until the page closes */
  }
  applyMode(mode);
}
