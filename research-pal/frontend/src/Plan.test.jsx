import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api.js", () => ({
  api: {
    plan: vi.fn(), makeDefaults: vi.fn(), addMilestone: vi.fn(), editMilestone: vi.fn(), deleteMilestone: vi.fn(), splitMilestone: vi.fn(), addTask: vi.fn(), editTask: vi.fn(),
    deleteTask: vi.fn(), weeklyReview: vi.fn(), saveReview: vi.fn(), journal: vi.fn(), addJournal: vi.fn(), deleteJournal: vi.fn(),
  },
}));
import { api } from "./api.js";
import Plan, { FridayReview, MoodChart } from "./Plan.jsx";

const TASKS = [
  { id: "t1", week: "2026-10-05", text: "Read two papers about the method.", done: false, ai: true, edited: false, label: "AI suggestion" },
  { id: "t2", week: "2026-10-12", text: "My own task", done: true, ai: false, edited: false, label: "" },
];
const PLAN = {
  today: "2026-10-09", week: "2026-10-05", current: "m1",
  milestones: [{ id: "m1", title: "First paper", due: "2026-12-15", done: false, days_left: 67, late: false, tasks: TASKS, tasks_done: 1 }],
};
const REVIEW = { week: "2026-10-05", this_week: null, reviews: [], due: true };

beforeEach(() => {
  vi.clearAllMocks();
  api.plan.mockResolvedValue(PLAN);
  api.weeklyReview.mockResolvedValue(REVIEW);
  api.journal.mockResolvedValue([]);
});

describe("Plan page", () => {
  it("shows the timeline, and labels a task of the AI", async () => {
    render(<Plan notify={() => {}} papers={[]} />);
    expect(await screen.findByRole("img", { name: /Timeline from today to .*First paper/ })).toBeInTheDocument();
    expect(screen.getByText("AI suggestion")).toBeInTheDocument(); // only the AI task has the label
    expect(screen.getByText(/1 of 2 tasks done/)).toBeInTheDocument();
    expect(screen.getByText(/67 days left/)).toBeInTheDocument();
  });
  it("offers the default milestones when there is none", async () => {
    api.plan.mockResolvedValue({ ...PLAN, milestones: [], current: null });
    api.makeDefaults.mockResolvedValue(PLAN);
    render(<Plan notify={() => {}} papers={[]} />);
    await userEvent.click(await screen.findByRole("button", { name: /Make the milestones for my stage/ }));
    expect(api.makeDefaults).toHaveBeenCalled();
  });
  it("asks the AI for weekly tasks and shows a kind text for a date that has passed", async () => {
    api.plan.mockResolvedValue({ ...PLAN, milestones: [{ ...PLAN.milestones[0], days_left: -3, late: true }] });
    api.splitMilestone.mockResolvedValue(PLAN);
    render(<Plan notify={() => {}} papers={[]} />);
    expect(await screen.findByText(/The date has passed. Change the date if your plan changed/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Suggest weekly tasks" }));
    expect(api.splitMilestone).toHaveBeenCalledWith("m1");
  });
  it("saves a task that the student wrote", async () => {
    api.editTask.mockResolvedValue({});
    render(<Plan notify={() => {}} papers={[]} />);
    const box = await screen.findByLabelText("Task: Read two papers about the method.");
    await userEvent.clear(box);
    await userEvent.type(box, "Read three papers");
    await userEvent.tab();
    expect(api.editTask).toHaveBeenCalledWith("t1", { text: "Read three papers" });
  });
  it("saves the weekly review and shows the points one time", async () => {
    api.saveReview.mockResolvedValue({ review: {}, xp_gained: 15 });
    render(<Plan notify={() => {}} papers={[]} />);
    await userEvent.type(await screen.findByLabelText("What did you do this week?"), "Read papers");
    await userEvent.click(screen.getByLabelText("Very good"));
    await userEvent.click(screen.getByRole("button", { name: "Save the review" }));
    expect(api.saveReview).toHaveBeenCalledWith(expect.objectContaining({ done: "Read papers", mood: 5 }));
    expect(await screen.findByText(/\+15 points/)).toBeInTheDocument();
  });
  it("writes a journal entry with a linked paper", async () => {
    api.addJournal.mockResolvedValue({ xp_gained: 3 });
    render(<Plan notify={() => {}} papers={[{ id: "p1", title: "AUTOMA" }]} />);
    await userEvent.selectOptions(await screen.findByLabelText("Kind"), "decision");
    await userEvent.type(screen.getByLabelText("Journal entry"), "I use two agents.");
    await userEvent.selectOptions(screen.getByLabelText("Link a paper"), "p1");
    await userEvent.click(screen.getByRole("button", { name: "Save the entry" }));
    expect(api.addJournal).toHaveBeenCalledWith({ kind: "decision", text: "I use two agents.", paper_ids: ["p1"] });
    expect(await screen.findByText(/\+3 points/)).toBeInTheDocument();
  });
});

describe("Weekly review on Today", () => {
  it("shows only when the review is due", async () => {
    api.weeklyReview.mockResolvedValue({ ...REVIEW, due: false });
    const { container } = render(<FridayReview notify={() => {}} />);
    await waitFor(() => expect(api.weeklyReview).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
  it("shows the form on Friday", async () => {
    render(<FridayReview notify={() => {}} />);
    expect(await screen.findByRole("region", { name: "Weekly review (5 minutes)" })).toBeInTheDocument();
  });
});

describe("Mood chart", () => {
  it("waits for 2 reviews and says that only the student sees it", () => {
    const { rerender } = render(<MoodChart reviews={[{ week: "2026-10-05", mood: 3 }]} />);
    expect(screen.getByText(/shows after 2 reviews/)).toBeInTheDocument();
    rerender(<MoodChart reviews={[{ week: "2026-09-28", mood: 2 }, { week: "2026-10-05", mood: 4 }]} />);
    expect(screen.getByRole("img", { name: /Mood by week: 2026-09-28 Low, 2026-10-05 Good/ })).toBeInTheDocument();
    expect(screen.getByText(/Only you see this/)).toBeInTheDocument();
  });
});
