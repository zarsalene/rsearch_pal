import { describe, expect, it } from "vitest";
import { LEVEL_STORY, LINES, MOOD, say, stage } from "./duck.js";

describe("the Duck", () => {
  it("says the same line for the same number, and goes through the list", () => {
    expect(say("right", 0)).toBe(say("right", 0));
    const seen = new Set([0, 1, 2, 3, 4, 5].map((n) => say("right", n)));
    expect(seen.size).toBe(LINES.right.length);
  });

  it("has a line for an event that it does not know", () => {
    expect(LINES.hello).toContain(say("nothing"));
  });

  it("never blames the student", () => {
    const text = Object.values(LINES).flat().join(" ").toLowerCase();
    for (const bad of ["failed", "stupid", "lazy", "wrong again", "you lost your", "shame"]) expect(text).not.toContain(bad);
    expect(LINES.lose.join(" ")).toMatch(/nothing is lost|not today/i);
  });

  it("writes short sentences (ASD-STE100: 20 words at most)", () => {
    for (const line of Object.values(LINES).flat()) for (const s of line.split(/(?<=[.!?])\s+/)) expect(s.split(/\s+/).length).toBeLessThanOrEqual(20);
  });

  it("has a mood for the events that show a face", () => {
    expect(MOOD.win).toBe("cheer");
    expect(MOOD.wrong).toBe("oops");
  });

  it("grows with the level", () => {
    expect([0, 1, 2, 3, 4, 5].map(stage)).toEqual(["duckling", "duckling", "duck", "duck", "scholar", "scholar"]);
  });

  it("has a story for each level of the server", () => {
    expect(Object.keys(LEVEL_STORY)).toEqual(["Explorer", "Reader", "Critic", "Connector", "Author", "Doctor"]);
  });
});
