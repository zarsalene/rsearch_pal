import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LevelToggle from "./LevelToggle.jsx";
import { setLevel, setSimpleEnabled } from "./level.js";
import SimpleText from "./SimpleText.jsx";

const ORIGINAL = "Precision is 91.4 percent. Recall is 95.0 percent.";
let n = 0;
const props = (load) => ({ text: ORIGINAL, load, cacheKey: "test-" + ++n }); // a new key for each test, so the page cache does not mix them

beforeEach(() => {
  setSimpleEnabled(true);
  setLevel("expert");
});

describe("SimpleText", () => {
  it("shows the original text in Expert mode and asks no server", () => {
    const load = vi.fn();
    render(<SimpleText {...props(load)} />);
    expect(screen.getByText(ORIGINAL)).toBeInTheDocument();
    expect(load).not.toHaveBeenCalled();
  });

  it("the Simple switch changes the text, and a link brings the original back", async () => {
    const user = userEvent.setup();
    const load = vi.fn().mockResolvedValue({ ok: true, text: "Precision is 91.4 percent. Recall is 95.0 percent. Both are high.", label: "AI simplification" });
    render(
      <>
        <LevelToggle />
        <SimpleText {...props(load)} />
      </>,
    );
    await user.click(screen.getByRole("radio", { name: "Simple" }));
    expect(await screen.findByText(/Both are high/)).toBeInTheDocument();
    expect(screen.getByText("AI simplification")).toBeInTheDocument();
    expect(localStorage.getItem("rp-level")).toBe("simple"); // the browser remembers it
    expect(load).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Show the original" }));
    expect(screen.getByText(ORIGINAL)).toBeInTheDocument();
    expect(screen.queryByText(/Both are high/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show the simple version" }));
    expect(screen.getByText(/Both are high/)).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "Expert" }));
    expect(screen.getByText(ORIGINAL)).toBeInTheDocument();
  });

  it("keeps the original and says why when the server refuses the simple version", async () => {
    setLevel("simple");
    const load = vi.fn().mockResolvedValue({ ok: false, text: ORIGINAL, message: "The server kept the original text. The simple version changed a number or a name." });
    render(<SimpleText {...props(load)} />);
    expect(await screen.findByText(/kept the original text/)).toBeInTheDocument();
    expect(screen.getByText(ORIGINAL)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show the original" })).not.toBeInTheDocument();
  });

  it("keeps the original when the server gives an error", async () => {
    setLevel("simple");
    render(<SimpleText {...props(vi.fn().mockRejectedValue(new Error("The AI is down.")))} />);
    expect(await screen.findByText(/The simple version is not available. The AI is down./)).toBeInTheDocument();
    expect(screen.getByText(ORIGINAL)).toBeInTheDocument();
  });

  it("shows the original while it waits", async () => {
    setLevel("simple");
    render(<SimpleText {...props(() => new Promise(() => {}))} />);
    expect(screen.getByText(ORIGINAL)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Making the simple version");
  });

  it("is always Expert when the feature switch is off", async () => {
    setLevel("simple");
    const load = vi.fn(() => new Promise(() => {}));
    render(<SimpleText {...props(load)} />);
    await act(async () => setSimpleEnabled(false));
    expect(screen.getByText(ORIGINAL)).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
