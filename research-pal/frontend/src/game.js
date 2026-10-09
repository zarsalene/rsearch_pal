// Helpers of the game page. The server decides the points. The page only shows them.

// The offset of the time zone of the student in minutes (for example 60 for UTC+1). The server uses it to find the day of an event.
export const tzMinutes = () => -new Date().getTimezoneOffset();

const SEEN = "rp-game-seen";

// What is new since the last visit: a new level or a new badge. The first visit shows nothing: there is nothing to compare.
export function newThings(summary) {
  let seen = null;
  try {
    seen = JSON.parse(localStorage.getItem(SEEN) || "null");
  } catch {
    seen = null;
  }
  const out = [];
  if (seen) {
    if (summary.level.index > seen.level) out.push({ kind: "level", text: `You are now a ${summary.level.name}.` });
    for (const b of summary.badges) if (!seen.badges.includes(b.code)) out.push({ kind: "badge", text: `New badge: ${b.name}.` });
  }
  try {
    localStorage.setItem(SEEN, JSON.stringify({ level: summary.level.index, badges: summary.badges.map((b) => b.code) }));
  } catch {
    /* private mode */
  }
  return out;
}

// Animations. The student can switch them off. The browser setting "reduce motion" also switches them off (see the CSS).
const ANIM = "rp-anim";
export const animationsOn = () => {
  try {
    return localStorage.getItem(ANIM) !== "off";
  } catch {
    return true;
  }
};
export function setAnimations(on) {
  try {
    localStorage.setItem(ANIM, on ? "on" : "off");
  } catch {
    /* private mode */
  }
  applyAnimations();
}
export function applyAnimations() {
  document.documentElement.setAttribute("data-anim", animationsOn() ? "on" : "off");
}

// "50 of 100 points" as a percent for a bar. A level has a floor (the points at its start) and the points of the next level.
export function levelPercent(xp, floor, nextTotal) {
  if (!nextTotal || nextTotal <= floor) return 100;
  return Math.max(0, Math.min(100, Math.round(((xp - floor) / (nextTotal - floor)) * 100)));
}
