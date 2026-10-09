import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ThesisBar from "./ThesisBar.jsx";

const PROJECT = { title: "Multi-agent threat hunting", question: "Do validation agents reduce false alarms?", stage: "year_1" };

function setup(props = {}) {
  const onSave = vi.fn().mockResolvedValue(true);
  const onOpenHelper = vi.fn();
  render(<ThesisBar project={PROJECT} onSave={onSave} onOpenHelper={onOpenHelper} {...props} />);
  return { onSave, onOpenHelper, user: userEvent.setup() };
}

describe("ThesisBar", () => {
  it("shows the title and the question", () => {
    setup();
    expect(screen.getByText("Multi-agent threat hunting")).toBeInTheDocument();
    expect(screen.getByText("Do validation agents reduce false alarms?")).toBeInTheDocument();
  });

  it("opens the edit field when you click it", async () => {
    const { user } = setup();
    expect(screen.queryByLabelText("Thesis title")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Edit your thesis/ }));
    expect(screen.getByLabelText("Thesis title")).toHaveValue("Multi-agent threat hunting");
    expect(screen.getByLabelText("Main question")).toHaveValue("Do validation agents reduce false alarms?");
  });

  it("sends the new text, and closes after the server saved it", async () => {
    const { user, onSave } = setup();
    await user.click(screen.getByRole("button", { name: /Edit your thesis/ }));
    const title = screen.getByLabelText("Thesis title");
    await user.clear(title);
    await user.type(title, "A new title");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenCalledWith({ title: "A new title", question: PROJECT.question });
    expect(screen.queryByLabelText("Thesis title")).not.toBeInTheDocument();
  });

  it("stays open when the server refuses, so the student does not lose the text", async () => {
    const { user } = setup({ onSave: vi.fn().mockResolvedValue(false) });
    await user.click(screen.getByRole("button", { name: /Edit your thesis/ }));
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByLabelText("Thesis title")).toBeInTheDocument();
  });

  it("cancel throws the change away", async () => {
    const { user, onSave } = setup();
    await user.click(screen.getByRole("button", { name: /Edit your thesis/ }));
    await user.type(screen.getByLabelText("Thesis title"), " more");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByText("Multi-agent threat hunting")).toBeInTheDocument();
  });

  it("asks for a title when there is none, and opens the helper", async () => {
    const { user, onOpenHelper } = setup({ project: { title: "", question: "", stage: "" } });
    expect(screen.getByText("Add your thesis title")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Edit your thesis/ }));
    await user.click(screen.getByRole("button", { name: "Open the question helper" }));
    expect(onOpenHelper).toHaveBeenCalled();
  });

  it("shows nothing while the project is not loaded", () => {
    const { container } = render(<ThesisBar project={null} onSave={() => {}} onOpenHelper={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
