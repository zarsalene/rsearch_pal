import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api.js", () => ({
  api: {
    questionCheck: vi.fn(), splitQuestion: vi.fn(), saveProject: vi.fn(), coverage: vi.fn(), projectHistory: vi.fn(),
    subQuestions: vi.fn(), addSubQuestion: vi.fn(), editSubQuestion: vi.fn(), deleteSubQuestion: vi.fn(),
  },
}));
import { api } from "./api.js";
import Project from "./Project.jsx";

const FINER = ["Feasible", "Interesting", "Novel", "Ethical", "Relevant"].map((name, i) => ({
  key: name.toLowerCase(), letter: "FINER"[i], name, rating: i === 0 ? "weak" : "ok", why: `${name} reason.`, label: "AI opinion",
}));
const CHECK = {
  question: "AI in health", finer: FINER, scope: { status: "too_wide", why: "The question covers a whole field.", label: "AI opinion" },
  versions: ["Can AI find lung cancer in X-ray images?", "Does AI cut the time of a diagnosis?", "How do nurses use AI tools?"].map((text) => ({ text, label: "AI suggestion" })),
  label: "AI suggestion",
};
const EMPTY = { title: "", question: "", stage: "", stages: [] };

function setup(props = {}) {
  const onProject = vi.fn();
  const onSubQuestions = vi.fn();
  const notify = vi.fn();
  render(<Project project={EMPTY} subQuestions={[]} onProject={onProject} onSubQuestions={onSubQuestions} notify={notify} {...props} />);
  return { onProject, onSubQuestions, notify, user: userEvent.setup() };
}

beforeEach(() => {
  vi.resetAllMocks();
  api.coverage.mockResolvedValue({ sub_questions: [], papers: 0, untagged: 0 });
  api.projectHistory.mockResolvedValue([]);
  api.subQuestions.mockResolvedValue([]);
});

async function writeAndCheck(user, text = "AI in health") {
  await user.type(screen.getByLabelText("Your question"), text);
  await user.click(screen.getByRole("button", { name: "Check my question" }));
}

describe("Project: the question helper", () => {
  it("shows the FINER check with five items, the scope, and labels the AI text as opinion", async () => {
    api.questionCheck.mockResolvedValue(CHECK);
    const { user } = setup();
    await writeAndCheck(user);
    expect(api.questionCheck).toHaveBeenCalledWith("AI in health");
    const list = await screen.findByRole("list", { name: "FINER check" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(5);
    expect(within(list).getByText("Feasible: Weak")).toBeInTheDocument();
    expect(within(list).getByText("Novel: OK")).toBeInTheDocument();
    expect(screen.getByText("Scope: too wide")).toBeInTheDocument();
    expect(screen.getByText("AI opinion")).toBeInTheDocument();
    expect(screen.queryByText(/looks good/)).not.toBeInTheDocument();
  });

  it("saves nothing while the student reads the check and the versions", async () => {
    api.questionCheck.mockResolvedValue(CHECK);
    const { user } = setup();
    await writeAndCheck(user);
    await user.click(await screen.findByRole("button", { name: "See narrower versions" }));
    expect(screen.getAllByText("AI suggestion")).toHaveLength(4); // the note, and one label for each of the 3 versions
    expect(api.saveProject).not.toHaveBeenCalled();
  });

  it("saves the version that the student chose, after the student edits it", async () => {
    api.questionCheck.mockResolvedValue(CHECK);
    api.saveProject.mockImplementation(async ({ question }) => ({ ...EMPTY, question }));
    const { user, onProject } = setup();
    await writeAndCheck(user);
    await user.click(await screen.findByRole("button", { name: "See narrower versions" }));
    await user.click(screen.getByRole("radio", { name: /lung cancer/ }));
    const box = screen.getByLabelText("Your main question");
    expect(box).toHaveValue("Can AI find lung cancer in X-ray images?");
    await user.type(box, " In adults?");
    await user.click(screen.getByRole("button", { name: "Save as my main question" }));
    expect(api.saveProject).toHaveBeenCalledWith({ question: "Can AI find lung cancer in X-ray images? In adults?" });
    expect(onProject).toHaveBeenCalled();
    expect(await screen.findByRole("heading", { name: "Your sub-questions" })).toBeInTheDocument(); // step 4
  });

  it("does not force a change when the question is good", async () => {
    api.questionCheck.mockResolvedValue({ ...CHECK, finer: FINER.map((i) => ({ ...i, rating: "ok" })), scope: { status: "ok", why: "", label: "AI opinion" } });
    api.saveProject.mockImplementation(async ({ question }) => ({ ...EMPTY, question }));
    const { user } = setup();
    await writeAndCheck(user, "Do validation agents reduce false alarms?");
    expect(await screen.findByText(/Your question looks good/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Keep my question" }));
    expect(api.saveProject).toHaveBeenCalledWith({ question: "AI in health" }); // the check result carries the question as the server cleaned it
    expect(await screen.findByRole("heading", { name: "Your sub-questions" })).toBeInTheDocument();
  });

  it("tells the student when the check fails, and keeps the text", async () => {
    api.questionCheck.mockRejectedValue(new Error("The AI provider is busy."));
    const { user, notify } = setup();
    await writeAndCheck(user);
    expect(notify).toHaveBeenCalledWith("The AI provider is busy.");
    expect(screen.getByLabelText("Your question")).toHaveValue("AI in health");
  });

  it("does not check a question that is too short", async () => {
    const { user } = setup();
    await user.type(screen.getByLabelText("Your question"), "AI");
    expect(screen.getByRole("button", { name: "Check my question" })).toBeDisabled();
  });
});

describe("Project: sub-questions", () => {
  const SAVED = { ...EMPTY, question: "Do validation agents reduce false alarms?" };

  async function openStep4(user) {
    await user.click(screen.getByRole("button", { name: "Go to the sub-questions" }));
  }

  it("shows the AI suggestions with a label, and adds only the one that the student picks", async () => {
    api.splitQuestion.mockResolvedValue({ sub_questions: [{ text: "What data exists?", label: "AI suggestion" }, { text: "Which method works?", label: "AI suggestion" }] });
    api.addSubQuestion.mockResolvedValue({ id: "a", text: "What data exists?", position: 0 });
    api.subQuestions.mockResolvedValue([{ id: "a", text: "What data exists?", position: 0 }]);
    const { user, onSubQuestions } = setup({ project: SAVED });
    await openStep4(user);
    await user.click(screen.getByRole("button", { name: "Suggest sub-questions" }));
    const list = await screen.findByRole("list", { name: "Suggested sub-questions" });
    expect(within(list).getAllByText("AI suggestion")).toHaveLength(2);
    expect(api.addSubQuestion).not.toHaveBeenCalled();
    await user.click(within(list).getAllByRole("button", { name: "Add" })[0]);
    expect(api.addSubQuestion).toHaveBeenCalledTimes(1);
    expect(api.addSubQuestion).toHaveBeenCalledWith("What data exists?");
    expect(onSubQuestions).toHaveBeenCalledWith([{ id: "a", text: "What data exists?", position: 0 }]);
    expect(within(screen.getByRole("list", { name: "Suggested sub-questions" })).getAllByRole("listitem")).toHaveLength(1); // the added one left the list
  });

  it("adds, edits and deletes a sub-question", async () => {
    api.addSubQuestion.mockResolvedValue({});
    api.editSubQuestion.mockResolvedValue({});
    api.deleteSubQuestion.mockResolvedValue({ ok: true });
    vi.stubGlobal("confirm", () => true);
    const { user } = setup({ project: SAVED, subQuestions: [{ id: "a", text: "Old text?", position: 0 }, { id: "b", text: "Second?", position: 1 }] });
    await openStep4(user);
    await user.type(screen.getByLabelText("New sub-question"), "My own?");
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(api.addSubQuestion).toHaveBeenCalledWith("My own?");

    const first = screen.getByLabelText("Sub-question 1");
    await user.clear(first);
    await user.type(first, "New text?");
    await user.tab();
    expect(api.editSubQuestion).toHaveBeenCalledWith("a", { text: "New text?" });

    await user.click(screen.getByRole("button", { name: "Move sub-question 1 down" }));
    expect(api.editSubQuestion).toHaveBeenLastCalledWith("a", { position: 1 });
    expect(screen.getByRole("button", { name: "Move sub-question 1 up" })).toBeDisabled(); // the first cannot go up

    await user.click(screen.getByRole("button", { name: "Delete sub-question 2" }));
    expect(api.deleteSubQuestion).toHaveBeenCalledWith("b");
    vi.unstubAllGlobals();
  });

  it("shows the coverage of each sub-question", async () => {
    api.coverage.mockResolvedValue({
      sub_questions: [{ id: "a", text: "What data exists?", papers: 3, level: "ok" }, { id: "b", text: "Which method works?", papers: 1, level: "thin" }, { id: "c", text: "How to measure?", papers: 0, level: "none" }],
      papers: 3, untagged: 1,
    });
    setup({ project: SAVED });
    expect(await screen.findByRole("img", { name: "SQ2: 1 paper" })).toBeInTheDocument();
    expect(screen.getByText("3 papers")).toBeInTheDocument();
    expect(screen.getByText("No paper yet")).toBeInTheDocument();
    expect(screen.getByText("1 paper has no sub-question yet.")).toBeInTheDocument();
  });

  it("shows the history of the title and the question", async () => {
    api.projectHistory.mockResolvedValue([{ id: 2, field: "question", old_value: "Old?", new_value: "New?", changed_at: 1760000000 }, { id: 1, field: "title", old_value: "", new_value: "First title", changed_at: 1750000000 }]);
    setup({ project: SAVED });
    expect(await screen.findByText("New?")).toBeInTheDocument();
    expect(screen.getByText("Before: Old?")).toBeInTheDocument();
    expect(screen.getByText("First title")).toBeInTheDocument();
  });
});
