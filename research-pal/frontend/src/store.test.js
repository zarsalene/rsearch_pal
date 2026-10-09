import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api.js", () => ({ api: { papers: vi.fn(async () => [{ id: "p1" }]), config: vi.fn(async () => ({})), features: vi.fn(async () => []) } }));

const phone = (matches) => (window.matchMedia = vi.fn(() => ({ matches, addEventListener() {}, removeEventListener() {} })));

describe("app store", () => {
  let useApp;
  beforeEach(async () => {
    phone(false);
    localStorage.clear();
    vi.resetModules();
    ({ useApp } = await import("./store.js"));
  });

  it("opens a paper and shows the card tab", () => {
    useApp.getState().setTab("chat");
    useApp.getState().openPaper("p1");
    expect(useApp.getState()).toMatchObject({ selected: "p1", tab: "cards" });
  });

  it("closes the library drawer on a phone, and does not save that choice", () => {
    phone(true);
    useApp.setState({ libOpen: true });
    useApp.getState().openPaper("p1");
    expect(useApp.getState().libOpen).toBe(false);
    expect(localStorage.getItem("rp-library")).toBeNull();
  });

  it("saves the choice of the library toggle", () => {
    useApp.setState({ libOpen: true });
    useApp.getState().toggleLibrary();
    expect(localStorage.getItem("rp-library")).toBe("closed");
  });

  it("clears the notice when the tab changes", () => {
    useApp.getState().notify("Problem");
    useApp.getState().setTab("search");
    expect(useApp.getState().notice).toBe("");
  });

  it("loads the papers", async () => {
    await useApp.getState().refresh();
    expect(useApp.getState().papers).toEqual([{ id: "p1" }]);
  });
});
