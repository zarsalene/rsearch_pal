import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api.js", () => ({ api: { focusStart: vi.fn(), focusStop: vi.fn() } }));
import { api } from "./api.js";
import FocusTimer from "./FocusTimer.jsx";
import { cleanMinutes, format, nextPhase, remainingMs } from "./timer.js";

describe("timer logic", () => {
  it("counts from the clock, not from ticks", () => {
    expect(remainingMs(1000, 1000, 25)).toBe(25 * 60000);
    expect(remainingMs(1000, 1000 + 10 * 60000, 25)).toBe(15 * 60000);
    expect(remainingMs(1000, 1000 + 99 * 60000, 25)).toBe(0); // never negative
  });
  it("shows minutes and seconds", () => {
    expect(format(25 * 60000)).toBe("25:00");
    expect(format(61 * 1000)).toBe("01:01");
    expect(format(400)).toBe("00:01"); // a part of a second counts as a second
    expect(format(0)).toBe("00:00");
  });
  it("work is followed by rest, and rest by waiting", () => {
    expect(nextPhase("work")).toBe("rest");
    expect(nextPhase("rest")).toBe("idle");
  });
  it("a wrong number of minutes gives the default", () => {
    expect(cleanMinutes("30", 25)).toBe(30);
    expect(cleanMinutes("0", 25)).toBe(25);
    expect(cleanMinutes("abc", 25)).toBe(25);
    expect(cleanMinutes("500", 25)).toBe(25);
  });
});

describe("FocusTimer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: false });
    vi.setSystemTime(new Date("2026-10-09T10:00:00"));
    api.focusStart.mockResolvedValue({ id: "s1", planned: 25, start: Date.now() / 1000 });
    api.focusStop.mockResolvedValue({ id: "s1", minutes: 25 });
  });
  afterEach(() => vi.useRealTimers());

  const setup = () => {
    const onChanged = vi.fn();
    render(<FocusTimer date="2026-10-09" goals={[]} papers={[]} active={null} onChanged={onChanged} notify={vi.fn()} />);
    return onChanged;
  };
  const advance = (ms) => act(async () => vi.advanceTimersByTimeAsync(ms));

  it("counts down, then switches to rest, then waits for the student", async () => {
    const onChanged = setup();
    await act(async () => screen.getByRole("button", { name: "Start 25 minutes" }).click());
    expect(api.focusStart).toHaveBeenCalledWith(expect.objectContaining({ planned_minutes: 25, date: "2026-10-09" }));
    expect(screen.getByRole("timer")).toHaveTextContent("25:00");

    await advance(10 * 60000);
    expect(screen.getByRole("timer")).toHaveTextContent("15:00");
    expect(screen.getByRole("timer")).toHaveTextContent("Focus");

    await advance(15 * 60000 + 1000); // the work ends
    expect(api.focusStop).toHaveBeenCalledTimes(1); // the server counts the minutes
    expect(onChanged).toHaveBeenCalled();
    expect(screen.getByRole("timer")).toHaveTextContent("Rest");
    expect(screen.getByRole("timer")).toHaveTextContent(/0[45]:\d\d/);
    expect(screen.getByRole("status")).toHaveTextContent("You focused for 25 minutes");

    await advance(5 * 60000 + 1000); // the rest ends
    expect(screen.queryByRole("timer")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start 25 minutes" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Start again when you are ready");
    expect(api.focusStop).toHaveBeenCalledTimes(1); // the rest is not recorded
  });

  it("is right after a long pause of the tab (the browser slows the ticks in the background)", async () => {
    setup();
    await act(async () => screen.getByRole("button", { name: "Start 25 minutes" }).click());
    vi.setSystemTime(Date.now() + 20 * 60000); // the clock goes on, no tick runs
    await advance(500);
    expect(screen.getByRole("timer")).toHaveTextContent("05:00");
  });

  it("the Stop button stops the session at once", async () => {
    setup();
    await act(async () => screen.getByRole("button", { name: "Start 25 minutes" }).click());
    api.focusStop.mockResolvedValue({ id: "s1", minutes: 3 });
    await act(async () => screen.getByRole("button", { name: "Stop" }).click());
    expect(api.focusStop).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("timer")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("You focused for 3 minutes");
  });

  it("goes on after a reload of the page when a session is running on the server", async () => {
    const start = Date.now() / 1000 - 10 * 60;
    render(<FocusTimer date="2026-10-09" goals={[]} papers={[]} active={{ id: "s1", start, planned: 25 }} onChanged={vi.fn()} notify={vi.fn()} />);
    expect(screen.getByRole("timer")).toHaveTextContent("15:00");
  });
});
