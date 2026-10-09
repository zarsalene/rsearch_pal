// The look of the avatar. It comes only from the level of the student. A new level adds one item. No item is ever removed.
export const ITEMS = [
  { level: 0, code: "backpack", name: "Backpack" },
  { level: 1, code: "glasses", name: "Glasses and a book" },
  { level: 2, code: "lens", name: "Magnifying glass" },
  { level: 3, code: "rope", name: "Rope with a knot" },
  { level: 4, code: "pen", name: "Pen and a scroll" },
  { level: 5, code: "cap", name: "Doctor cap and a gold star" },
];

export function lookFor(levelIndex) {
  const i = Number.isInteger(levelIndex) && levelIndex >= 0 ? Math.min(levelIndex, ITEMS.length - 1) : 0;
  return { level: i, items: ITEMS.filter((it) => it.level <= i).map((it) => it.code), next: ITEMS[i + 1] || null };
}

export function webglOk() {
  try {
    const c = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
  } catch {
    return false;
  }
}

const KEY = "rp-avatar";
export const avatarShown = () => {
  try {
    return localStorage.getItem(KEY) !== "off";
  } catch {
    return true;
  }
};
export function setAvatarShown(on) {
  try {
    localStorage.setItem(KEY, on ? "on" : "off");
  } catch {
    /* private mode: the choice lasts until the page closes */
  }
}
