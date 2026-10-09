import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, vi } from "vitest";
import { cleanup, configure } from "@testing-library/react";

// A slow computer (or a busy CI machine) must not make a test fail: wait up to 5 seconds for a change on the page.
configure({ asyncUtilTimeout: 5000 });

// jsdom has no canvas. The island and the avatar do not need it in a test, so we keep the log clean.
HTMLCanvasElement.prototype.getContext = () => null;

// jsdom has no matchMedia. The theme code needs it. The test device uses the light theme.
beforeEach(() => {
  window.matchMedia = vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

afterEach(() => cleanup());
