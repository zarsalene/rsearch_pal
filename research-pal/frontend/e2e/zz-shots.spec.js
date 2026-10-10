import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PDF = path.join(path.dirname(fileURLToPath(import.meta.url)), ".generated", "a.pdf");
const OUT = "C:/Users/zarsa/AppData/Local/Temp/claude/c--Users-zarsa-Desktop-Work-research-pal-research-pal/0e00d814-4dc0-46b3-a635-005901d053d1/scratchpad/shots";
const RIGHT = /Analysts spend many hours|Our system uses a hypothesis|AUTOMA reaches a precision/;

async function signInAndLoad(page) {
  const loaded = page.waitForResponse((r) => r.url().endsWith("/api/papers") && r.request().method() === "GET");
  await signIn(page);
  return (await loaded).json();
}
async function signIn(page) {
  await page.goto("/");
  await page.getByLabel("Password").fill("e2e-password-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("tab", { name: "Settings" })).toBeVisible();
}
const shot = (page, name) => page.screenshot({ path: `${OUT}/${name}.png`, fullPage: false });

const MAP = {
  nodes: [
    { id: "n1", title: "AUTOMA: Multi-agent threat hunting", verdict: "read", keywords: [], rank: 3, boss_won: true },
    { id: "n2", title: "Hypothesis generation with LLM agents", verdict: "read", keywords: [], rank: 2, boss_won: false },
    { id: "n3", title: "Sysmon log analysis at scale", verdict: "skim", keywords: [], rank: 1, boss_won: false },
    { id: "n4", title: "Provenance graphs for APT detection", verdict: "read", keywords: [], rank: 0, boss_won: false },
    { id: "n5", title: "Alert triage with transformers", verdict: "skim", keywords: [], rank: 1, boss_won: false },
  ],
  edges: [
    { source: "n1", target: "n2", sim: 0.62, shared: ["threat hunting"], state: "found", relation: "same_problem", summary: "Both papers use agents for threat hunting." },
    { source: "n2", target: "n3", sim: 0.41, shared: [], state: "fog", relation: "", summary: "" },
    { source: "n1", target: "n4", sim: 0.38, shared: ["APT"], state: "fog", relation: "", summary: "" },
    { source: "n4", target: "n5", sim: 0.33, shared: [], state: "unclear", relation: "", summary: "" },
    { source: "n3", target: "n5", sim: 0.45, shared: ["logs"], state: "fog", relation: "", summary: "" },
  ],
  stats: { found: 1, fog: 3, unclear: 1 },
};

test.describe.serial("screenshots", () => {
  test("desktop light", async ({ page }) => {
    test.setTimeout(240000);
    await page.setViewportSize({ width: 1280, height: 820 });
    const papers = await signInAndLoad(page);
    if (papers.length) await page.getByRole("button", { name: "Add paper" }).click();
    await page.locator('input[type="file"]').setInputFiles(PDF);
    await page.getByRole("button", { name: "Read the paper" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toContainText("AUTOMA");
    await expect(page.getByRole("button", { name: "Fight the boss" })).toBeVisible();
    await page.waitForTimeout(1500);
    await shot(page, "01-card-bossbar");

    await page.getByRole("button", { name: "Fight the boss" }).click();
    const fight = page.getByRole("dialog", { name: /Boss fight/ });
    await expect(fight.getByRole("heading", { name: /Round 1/ })).toBeVisible();
    await page.waitForTimeout(600);
    await shot(page, "02-battle-question");
    await fight.getByRole("button", { name: RIGHT }).click();
    await expect(fight.getByText(/Right!/)).toBeVisible();
    await page.waitForTimeout(900);
    await shot(page, "03-battle-feedback");
    await fight.getByRole("button", { name: "Next question" }).click();
    // a wrong answer for the second question
    await fight.getByRole("button", { name: /A recipe|A law|A new kind/ }).first().click();
    await expect(fight.getByText(/Not this time/)).toBeVisible();
    await page.waitForTimeout(700);
    await shot(page, "04-battle-wrong");
    await fight.getByRole("button", { name: "Next question" }).click();
    await fight.getByRole("button", { name: RIGHT }).click();
    await fight.getByRole("button", { name: /See the result/ }).click();
    await page.waitForTimeout(1600);
    await shot(page, "05-battle-end");
    await fight.getByRole("button", { name: "Back to the card" }).click();
    await page.waitForTimeout(1200);

    await page.getByRole("tab", { name: "Play" }).click();
    await page.waitForTimeout(1200);
    await shot(page, "06-play-home");
    await page.getByRole("radio", { name: "Cards" }).click();
    await page.waitForTimeout(900);
    await shot(page, "07-cards");

    await page.route("**/api/game/map", (route) => route.fulfill({ json: MAP }));
    await page.getByRole("radio", { name: "Map" }).click();
    await page.waitForTimeout(1800);
    await shot(page, "08-map");
    await page.locator(".fmark.fog").first().click();
    await page.waitForTimeout(500);
    await shot(page, "09-map-selected");

    await page.getByRole("radio", { name: "Shop" }).click();
    await page.waitForTimeout(700);
    await shot(page, "10-shop");

    await page.getByRole("radio", { name: "Semester" }).click();
    await page.waitForTimeout(500);
    await shot(page, "11-sem-start");
    await page.getByRole("button", { name: /Start a semester/ }).click();
    await page.waitForTimeout(800);
    await page.getByRole("button", { name: /^Read papers/ }).click();
    await page.getByRole("button", { name: /^Run a test/ }).click();
    await page.waitForTimeout(600);
    await shot(page, "12-sem-run");

    // play the whole semester: read, test, rest, end the week. Answer each event with the first choice.
    for (let i = 0; i < 80; i++) {
      if (await page.locator(".report").isVisible().catch(() => false)) break;
      const event = page.locator(".event");
      if (await event.isVisible().catch(() => false)) {
        if (i < 12) {
          await page.waitForTimeout(300);
          await shot(page, "13-sem-event");
        }
        await event.getByRole("button").first().click();
        await page.waitForTimeout(250);
        continue;
      }
      for (const name of [/^Read papers/, /^Run a test/, /^Rest/]) {
        const b = page.getByRole("button", { name });
        if ((await b.isVisible().catch(() => false)) && (await b.isEnabled().catch(() => false))) await b.click().catch(() => {});
      }
      await page.getByRole("button", { name: /End the week/ }).click().catch(() => {});
      await page.waitForTimeout(200);
    }
    await page.waitForTimeout(1200);
    await shot(page, "14-sem-report");
  });

  test("phone and dark", async ({ browser }) => {
    test.setTimeout(120000);
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, colorScheme: "dark" });
    const page = await ctx.newPage();
    await signIn(page);
    await page.getByRole("tab", { name: "Play" }).click();
    await page.waitForTimeout(1500);
    await shot(page, "20-phone-play-home");
    await page.getByRole("radio", { name: "Semester" }).click();
    await page.getByRole("button", { name: /Start a semester/ }).click();
    await page.waitForTimeout(900);
    await shot(page, "21-phone-sem");
    await page.getByRole("radio", { name: "Cards" }).click();
    await page.waitForTimeout(900);
    await shot(page, "22-phone-cards");
    await page.getByRole("button", { name: /Fight again/ }).first().click();
    await page.waitForTimeout(1500);
    await shot(page, "23-phone-battle");
    await ctx.close();
  });
});
