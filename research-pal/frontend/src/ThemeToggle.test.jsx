import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import ThemeToggle from "./ThemeToggle.jsx";

describe("ThemeToggle", () => {
  it("changes the theme and saves the choice in the browser", async () => {
    const user = userEvent.setup();
    render(<ThemeToggle />);
    expect(screen.getByRole("radio", { name: "Match my device" })).toBeChecked(); // the start choice

    await user.click(screen.getByRole("radio", { name: "Dark" }));
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(localStorage.getItem("rp-theme")).toBe("dark");
    expect(screen.getByRole("radio", { name: "Dark" })).toBeChecked();

    await user.click(screen.getByRole("radio", { name: "Light" }));
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    expect(localStorage.getItem("rp-theme")).toBe("light");
  });

  it("follows the device in System mode", async () => {
    const user = userEvent.setup();
    window.matchMedia = () => ({ matches: true, addEventListener() {}, removeEventListener() {} }); // the device is dark
    render(<ThemeToggle />);
    await user.click(screen.getByRole("radio", { name: "Dark" }));
    await user.click(screen.getByRole("radio", { name: "Match my device" }));
    expect(localStorage.getItem("rp-theme")).toBeNull();
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  });
});
