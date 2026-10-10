// Sound, feeling and confetti for the game. Small and safe: if a browser cannot do one thing, nothing happens and nothing breaks.
// The student can switch sound off, and "calm" mode switches off confetti and shaking. Both choices stay in this browser.
import { buzz } from "./native.js";

const get = (key, fallback) => {
  try {
    return localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
};

export function getPrefs() {
  return {
    sound: get("rp-sound", "on") !== "off",
    // Calm mode starts on when the phone asks to reduce motion.
    calm: get("rp-calm", typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ? "on" : "off") === "on",
  };
}

export function savePref(name, on) {
  try {
    localStorage.setItem(name === "sound" ? "rp-sound" : "rp-calm", name === "sound" ? (on ? "on" : "off") : on ? "on" : "off");
  } catch {}
}

let ctx = null;
function audio() {
  if (typeof window === "undefined") return null;
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return null;
  try {
    ctx ||= new AC();
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  } catch {
    return null;
  }
}

// [frequency, start, length, options]. Short, soft notes. The master volume is low.
const SOUNDS = {
  tap: [[880, 0, 0.05, { type: "triangle", vol: 0.04 }]],
  correct: [[660, 0, 0.09], [990, 0.09, 0.18]],
  wrong: [[220, 0, 0.18, { type: "triangle", vol: 0.09 }], [165, 0.11, 0.24, { type: "triangle", vol: 0.07 }]],
  crit: [[660, 0, 0.07], [880, 0.07, 0.07], [1320, 0.14, 0.22, { type: "square", vol: 0.05 }]],
  win: [[523, 0, 0.12], [659, 0.12, 0.12], [784, 0.24, 0.12], [1047, 0.36, 0.45]],
  lose: [[330, 0, 0.2, { type: "triangle" }], [262, 0.2, 0.35, { type: "triangle" }]],
  level: [[392, 0, 0.12], [523, 0.12, 0.12], [659, 0.24, 0.12], [784, 0.36, 0.12], [1047, 0.48, 0.55]],
  spark: [[1568, 0, 0.06, { type: "triangle" }], [2093, 0.06, 0.14, { type: "triangle" }]],
  event: [[440, 0, 0.1], [587, 0.1, 0.18]],
};
const FEEL = { tap: "light", correct: "light", crit: "success", win: "success", level: "success", wrong: "warn", lose: "warn" };

export function play(name) {
  const notes = SOUNDS[name];
  if (!notes) return;
  if (FEEL[name]) buzz(FEEL[name]);
  if (!getPrefs().sound) return;
  const a = audio();
  if (!a) return;
  try {
    for (const [freq, start, len, o = {}] of notes) {
      const t = a.currentTime + start;
      const osc = a.createOscillator();
      const gain = a.createGain();
      osc.type = o.type || "sine";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(o.vol ?? 0.11, t + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + len);
      osc.connect(gain).connect(a.destination);
      osc.start(t);
      osc.stop(t + len + 0.03);
    }
  } catch {}
}

// Confetti is drawn by <Confetti /> (it listens to this event). In calm mode there is none.
export function confetti(power = "small") {
  if (typeof window === "undefined" || getPrefs().calm) return;
  window.dispatchEvent(new CustomEvent("rp-confetti", { detail: { power } }));
}
