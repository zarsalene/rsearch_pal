import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api.js", () => ({ api: { rateReview: vi.fn(), openPdf: vi.fn().mockResolvedValue(), reviewGarden: vi.fn(), reviewDue: vi.fn() } }));
import { api } from "./api.js";
import { MapView } from "./ExpeditionMap.jsx";
import Review, { Garden, ReviewSession } from "./Review.jsx";

const ITEMS = [
  { id: "i1", kind: "idea", kind_label: "Main idea", label: "Main idea", paper_id: "p1", title: "AUTOMA", question: 'What is the main idea of "AUTOMA"?', answer: "Two agents work together.", quote: "Our system uses a hypothesis agent and a validation agent.", page: 2 },
  { id: "i2", kind: "glossary", kind_label: "Word", label: "AI explanation", paper_id: "p1", title: "AUTOMA", question: 'What does "ontology" mean?', answer: "A map of ideas.", quote: "", page: 0 },
];

beforeEach(() => vi.clearAllMocks());

describe("review session", () => {
  it("hides the answer first, then shows it with the quote, then the 4 buttons", async () => {
    const user = userEvent.setup();
    api.rateReview.mockResolvedValue({ xp_gained: 2, remaining: 1 });
    render(<ReviewSession items={ITEMS} onDone={() => {}} notify={vi.fn()} />);
    expect(screen.getByText(/What is the main idea of "AUTOMA"/)).toBeInTheDocument();
    expect(screen.queryByText("Two agents work together.")).not.toBeInTheDocument(); // the student thinks first
    expect(screen.queryByRole("button", { name: "Good" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Show answer" }));
    expect(screen.getByText("Two agents work together.")).toBeInTheDocument();
    expect(screen.getByText(/hypothesis agent and a validation agent/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "p. 2" })).toBeInTheDocument();
    for (const name of ["Again", "Hard", "Good", "Easy"]) expect(screen.getByRole("button", { name })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Good" }));
    expect(api.rateReview).toHaveBeenCalledWith("i1", "good", expect.stringMatching(/^\d{4}-\d\d-\d\d$/));
    expect(screen.getByText(/Item 2 of 2/)).toBeInTheDocument();
    expect(screen.queryByText("A map of ideas.")).not.toBeInTheDocument(); // the next answer is hidden again
  });

  it("a word that the AI explained has the label AI explanation and no quote", async () => {
    const user = userEvent.setup();
    render(<ReviewSession items={[ITEMS[1]]} onDone={() => {}} notify={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Show answer" }));
    expect(screen.getByText("AI explanation")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /p\./ })).not.toBeInTheDocument();
  });

  it("ends with a kind summary and the points", async () => {
    const user = userEvent.setup();
    api.rateReview.mockResolvedValue({ xp_gained: 2, remaining: 0 });
    const onDone = vi.fn();
    render(<ReviewSession items={[ITEMS[0]]} onDone={onDone} notify={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Show answer" }));
    await user.click(screen.getByRole("button", { name: "Easy" }));
    expect(screen.getByRole("status")).toHaveTextContent("You reviewed 1 item. +2 points. Your plants are fresh.");
    await user.click(screen.getByRole("button", { name: "Back to the garden" }));
    expect(onDone).toHaveBeenCalled();
  });
});

describe("garden", () => {
  const PLANTS = [
    { paper_id: "a", title: "Fresh paper", state: "fresh", due: 0, items: 2 },
    { paper_id: "b", title: "Thirsty paper", state: "ok", due: 3, items: 3 },
    { paper_id: "c", title: "Old paper", state: "dry", due: 1, items: 1 },
  ];
  it("shows one plant for each paper, with calm words", () => {
    render(<Garden plants={PLANTS} onPick={() => {}} />);
    expect(screen.getByRole("button", { name: /Fresh paper: Fresh/ })).toHaveClass("fresh");
    expect(screen.getByRole("button", { name: /Thirsty paper: Needs water, 3 due/ })).toHaveClass("ok");
    expect(screen.getByRole("button", { name: /Old paper: A little dry/ })).toHaveClass("dry");
    expect(screen.queryByText(/dead|dying|late|overdue/i)).not.toBeInTheDocument();
  });
  it("a click on a plant starts the review of this paper", async () => {
    const onPick = vi.fn();
    render(<Garden plants={PLANTS} onPick={onPick} />);
    await userEvent.setup().click(screen.getByRole("button", { name: /Thirsty paper/ }));
    expect(onPick).toHaveBeenCalledWith(PLANTS[1]);
  });
  it("the review page: a click on a fresh plant says that nothing is due", async () => {
    api.reviewGarden.mockResolvedValue({ due_total: 0, plants: [{ paper_id: "a", title: "Fresh paper", state: "fresh", due: 0, items: 2 }] });
    api.reviewDue.mockResolvedValue({ total: 0, items: [] });
    render(<Review notify={vi.fn()} />);
    expect(await screen.findByRole("button", { name: "Nothing is due today" })).toBeDisabled();
    await userEvent.setup().click(screen.getByRole("button", { name: /Fresh paper/ }));
    expect(await screen.findByText(/This plant is fresh. Nothing is due/)).toBeInTheDocument();
  });
});

describe("Expedition map", () => {
  const MAP = {
    total: 17,
    regions: [
      { code: "peak", name: "Question Peak", percent: 100, state: "done", target: "project", first_step: "Your question is clear. Keep it in view.", detail: "Title yes, question yes, 3 sub-questions." },
      { code: "forest", name: "Literature Forest", percent: 40, state: "growing", target: "cards", first_step: "Read a paper for SQ2, tag it, and explain it in your own words.", detail: "2 cards." },
      { code: "workshop", name: "Method Workshop", percent: 0, state: "not_started", target: "today", first_step: "The research journal comes in a later sprint. Then you can write your methods here.", detail: "Not available yet." },
      { code: "mines", name: "Data Mines", percent: 0, state: "not_started", target: "today", first_step: "x", detail: "" },
      { code: "coast", name: "Writing Coast", percent: 0, state: "not_started", target: "today", first_step: "y", detail: "" },
      { code: "castle", name: "Defense Castle", percent: 0, state: "not_started", target: "today", first_step: "z", detail: "" },
    ],
  };
  it("shows the six regions with their percent. A region at 0% is Not started, with a first step.", async () => {
    const onGo = vi.fn();
    const user = userEvent.setup();
    render(<MapView map={MAP} onGo={onGo} />);
    expect(screen.getByRole("group", { name: /Map of the PhD road: Question Peak 100%, Literature Forest 40%/ })).toBeInTheDocument();
    for (const r of MAP.regions) expect(screen.getAllByRole("button", { name: new RegExp(r.name) }).length).toBeGreaterThanOrEqual(1); // the picture and the list
    expect(screen.getAllByText(/Not started/).length).toBeGreaterThanOrEqual(4);

    await user.click(screen.getAllByRole("button", { name: /Method Workshop/ })[0]);
    const detail = screen.getByRole("region", { name: "Method Workshop: what to do" });
    expect(within(detail).getByText(/research journal comes in a later sprint/)).toBeInTheDocument();
    await user.click(within(detail).getByRole("button", { name: "Go there" }));
    expect(onGo).toHaveBeenCalledWith("today");
  });
});
