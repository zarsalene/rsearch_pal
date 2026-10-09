// Expert or Simple. The choice is saved in this browser. In Simple mode, the texts of the AI show their simple version.
// The switch "Simple mode" in Settings → Features can turn the whole function off. Then the level is always Expert.
import { useSyncExternalStore } from "react";

const KEY = "rp-level";
const listeners = new Set();
let enabled = true;
let memory = ""; // used only when the browser cannot save the choice

const emit = () => listeners.forEach((f) => f());
const stored = () => {
  try {
    return localStorage.getItem(KEY) === "simple" ? "simple" : "expert";
  } catch {
    return "expert";
  }
};

export function setLevel(level) {
  try {
    localStorage.setItem(KEY, level === "simple" ? "simple" : "expert");
  } catch {
    /* private mode: the choice lasts until the page closes */
    memory = level === "simple" ? "simple" : "expert";
  }
  emit();
}

export function setSimpleEnabled(on) {
  if (enabled !== !!on) {
    enabled = !!on;
    emit();
  }
}

export function getLevel() {
  if (!enabled) return "expert";
  return memory || stored();
}

export function useLevel() {
  return useSyncExternalStore((cb) => (listeners.add(cb), () => listeners.delete(cb)), getLevel, () => "expert");
}
