import { beforeEach, describe, expect, it, vi } from "vitest";
import { confetti, getPrefs, play, savePref } from "./juice.js";

describe("sound and calm mode", () => {
  beforeEach(() => localStorage.clear());

  it("starts with sound on and calm mode off", () => {
    expect(getPrefs()).toEqual({ sound: true, calm: false });
  });

  it("saves the choices", () => {
    savePref("sound", false);
    savePref("calm", true);
    expect(getPrefs()).toEqual({ sound: false, calm: true });
    expect(localStorage.getItem("rp-sound")).toBe("off");
  });

  it("starts calm when the phone asks to reduce motion", () => {
    window.matchMedia = vi.fn(() => ({ matches: true, addEventListener() {}, removeEventListener() {} }));
    expect(getPrefs().calm).toBe(true);
    savePref("calm", false); // the choice of the student wins
    expect(getPrefs().calm).toBe(false);
  });

  it("plays nothing, and does not break, when the browser has no audio", () => {
    expect(() => ["tap", "correct", "wrong", "win", "level", "nope"].forEach(play)).not.toThrow();
  });

  it("sends the confetti event, but not in calm mode", () => {
    const got = vi.fn();
    window.addEventListener("rp-confetti", got);
    confetti("big");
    expect(got).toHaveBeenCalledTimes(1);
    expect(got.mock.calls[0][0].detail).toEqual({ power: "big" });
    savePref("calm", true);
    confetti("big");
    expect(got).toHaveBeenCalledTimes(1);
    window.removeEventListener("rp-confetti", got);
  });
});
