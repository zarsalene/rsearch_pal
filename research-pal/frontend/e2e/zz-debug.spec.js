import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PDF = path.join(path.dirname(fileURLToPath(import.meta.url)), ".generated", "a.pdf");
const MAP = {
  nodes: [
    { id: "n1", title: "AUTOMA", verdict: "read", keywords: [], rank: 3, boss_won: true },
    { id: "n2", title: "Hypothesis generation", verdict: "read", keywords: [], rank: 2, boss_won: false },
    { id: "n3", title: "Sysmon logs", verdict: "skim", keywords: [], rank: 1, boss_won: false },
  ],
  edges: [
    { source: "n1", target: "n2", sim: 0.62, shared: [], state: "found", relation: "same_problem", summary: "x" },
    { source: "n2", target: "n3", sim: 0.41, shared: [], state: "fog", relation: "", summary: "" },
  ],
  stats: { found: 1, fog: 1, unclear: 0 },
};

test("debug the map hit test", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/");
  await page.getByLabel("Password").fill("e2e-password-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("tab", { name: "Settings" })).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles(PDF);
  await page.getByRole("button", { name: "Read the paper", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("AUTOMA");
  await page.route("**/api/game/map", (route) => route.fulfill({ json: MAP }));
  await page.getByRole("tab", { name: "Play" }).click();
  await page.getByRole("radio", { name: "Map" }).click();
  await page.waitForTimeout(2500);
  const info = await page.evaluate(() => {
    const out = [];
    for (const g of document.querySelectorAll(".fmark")) {
      const r = g.getBoundingClientRect();
      const cx = r.x + r.width / 2;
      const cy = r.y + r.height / 2;
      const hit = document.elementFromPoint(cx, cy);
      const c = g.querySelector("circle").getBoundingClientRect();
      out.push({ cls: g.getAttribute("class"), box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)], circle: [Math.round(c.x), Math.round(c.y), Math.round(c.width), Math.round(c.height)], hit: hit && (hit.tagName + "." + hit.getAttribute("class")), inView: cy < innerHeight });
    }
    return out;
  });
  console.log("HITTEST " + JSON.stringify(info));
});
