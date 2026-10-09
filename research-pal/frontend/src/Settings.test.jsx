import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("./api.js", () => ({ api: { setFeatures: vi.fn() } }));
import { api } from "./api.js";
import Settings from "./Settings.jsx";

const FEATURES = [{ name: "chat", label: "Chat", description: "Ask questions about your papers.", enabled: true }];

function setup(props = {}) {
  const onFeatures = vi.fn();
  const notify = vi.fn();
  render(<Settings config={{ provider: "gemini", model: "test-model", llm_ready: true }} features={FEATURES} onConfig={() => {}} onFeatures={onFeatures} onImported={() => {}} onLogout={() => {}} notify={notify} {...props} />);
  return { onFeatures, notify };
}

describe("Settings: feature switches", () => {
  it("shows one switch for each feature", () => {
    setup();
    expect(screen.getByRole("switch", { name: /Chat/ })).toBeChecked();
  });

  it("sends the new value to the server and shows the list that comes back", async () => {
    api.setFeatures.mockResolvedValue([{ ...FEATURES[0], enabled: false }]);
    const { onFeatures } = setup();
    await userEvent.setup().click(screen.getByRole("switch", { name: /Chat/ }));
    expect(api.setFeatures).toHaveBeenCalledWith({ chat: false });
    expect(onFeatures).toHaveBeenCalledWith([{ ...FEATURES[0], enabled: false }]);
  });

  it("tells the student when the server refuses", async () => {
    api.setFeatures.mockRejectedValue(new Error("Unknown feature: chat"));
    const { notify, onFeatures } = setup();
    await userEvent.setup().click(screen.getByRole("switch", { name: /Chat/ }));
    expect(notify).toHaveBeenCalledWith("Unknown feature: chat");
    expect(onFeatures).not.toHaveBeenCalled();
  });

  it("shows no Features section while the list is not loaded", () => {
    setup({ features: null });
    expect(screen.queryByText("Features")).not.toBeInTheDocument();
  });
});
