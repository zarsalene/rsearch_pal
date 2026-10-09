// The logic of the focus timer. It uses the clock, not a count of ticks, so it stays right when the browser tab is in the background.

export const DEFAULTS = { work: 25, rest: 5 };

// The time that is left, in milliseconds. startMs is the start of the phase.
export function remainingMs(startMs, nowMs, minutes) {
  return Math.max(0, startMs + minutes * 60000 - nowMs);
}

// 1500000 -> "25:00". A part of a second counts as a whole second, so the timer never shows 00:00 before the end.
export function format(ms) {
  const s = Math.ceil(ms / 1000);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

// The phase after the end of this phase. After the work comes the rest. After the rest the timer waits for the student.
export function nextPhase(phase) {
  return phase === "work" ? "rest" : "idle";
}

// A number of minutes that the student typed. A wrong value gives the default.
export function cleanMinutes(value, fallback, min = 1, max = 180) {
  const n = Math.round(Number(value));
  return Number.isFinite(n) && n >= min && n <= max ? n : fallback;
}

// A short sound at the end. It needs no file. It can fail in a browser without sound: then nothing happens.
export function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = 660;
    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.8);
    osc.connect(gain).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.8);
  } catch {
    /* no sound */
  }
}
