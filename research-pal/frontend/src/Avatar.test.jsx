import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import AvatarCard from "./Avatar3D.jsx";
import { ITEMS, lookFor } from "./avatar.js";

beforeEach(() => localStorage.clear());

describe("the look of the avatar", () => {
  it("gives only the items of the level and of the levels before it", () => {
    expect(lookFor(0).items).toEqual(["backpack"]);
    expect(lookFor(2).items).toEqual(["backpack", "glasses", "lens"]);
    expect(lookFor(5).items).toHaveLength(ITEMS.length);
  });
  it("gives the Explorer look for an unknown level, and names the next item", () => {
    expect(lookFor(undefined).items).toEqual(["backpack"]);
    expect(lookFor(-3).level).toBe(0);
    expect(lookFor(99).level).toBe(5);
    expect(lookFor(1).next.name).toBe("Magnifying glass");
    expect(lookFor(5).next).toBeNull();
  });
  it("never removes an item when the level goes up", () => {
    for (let i = 0; i < 5; i++) expect(lookFor(i + 1).items).toEqual(expect.arrayContaining(lookFor(i).items));
  });
});

describe("the avatar card", () => {
  it("shows the flat picture when the browser has no WebGL (jsdom has none)", () => {
    render(<AvatarCard level={1} />);
    expect(screen.getByRole("img", { name: /Avatar with: backpack, glasses/ })).toBeInTheDocument();
    expect(screen.getByText(/At the next level you get: Magnifying glass/)).toBeInTheDocument();
  });
  it("hides the avatar and keeps the choice", async () => {
    const { unmount } = render(<AvatarCard level={0} />);
    await userEvent.click(screen.getByRole("button", { name: "Hide avatar" }));
    expect(screen.getByText("The avatar is hidden.")).toBeInTheDocument();
    unmount();
    render(<AvatarCard level={0} />);
    expect(screen.getByText("The avatar is hidden.")).toBeInTheDocument();
  });
  it("says thank you at the last level", () => {
    render(<AvatarCard level={5} />);
    expect(screen.getByText(/all the items/)).toBeInTheDocument();
  });
});
