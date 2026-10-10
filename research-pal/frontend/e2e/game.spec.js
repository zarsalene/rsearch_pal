import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PDF = path.join(path.dirname(fileURLToPath(import.meta.url)), ".generated", "a.pdf");
const PASSWORD = "e2e-password-123";

async function signIn(page) {
  await page.goto("/");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("tab", { name: "Settings" })).toBeVisible();
}

// The fake AI of the test server writes one question for each checked quote. The right answer is the first words of the quote.
const RIGHT = /Analysts spend many hours|Our system uses a hypothesis|AUTOMA reaches a precision/;

test.describe.serial("The game", () => {
  test("fight the boss of a paper: the questions come from checked quotes, and the win is shown", async ({ page }) => {
    await signIn(page);
    await page.locator('input[type="file"]').setInputFiles(PDF);
    await page.getByRole("button", { name: "Read the paper" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toContainText("AUTOMA: Multi-agent threat hunting");

    await page.getByRole("button", { name: "Fight the boss" }).click();
    const fight = page.getByRole("dialog", { name: /Boss fight: AUTOMA/ });
    await expect(fight.getByRole("img", { name: "3 of 3 hearts left" })).toBeVisible();

    for (let i = 0; i < 3; i++) {
      await expect(fight.getByRole("heading", { name: new RegExp(`Round 1. What does passage ${i + 1}`) })).toBeVisible();
      await fight.getByRole("button", { name: RIGHT }).click();
      await expect(fight.getByText(/Right! −\d+ HP|Combo hit!/)).toBeVisible();
      // the proof of the answer: a quote from the PDF with its page
      await expect(fight.getByRole("button", { name: /Proof · p\. \d/ })).toBeVisible();
      await fight.getByRole("button", { name: i < 2 ? "Next question" : "See the result" }).click();
    }
    await expect(fight.getByRole("heading", { name: "Flawless victory!" })).toBeVisible();
    await fight.getByRole("button", { name: "Back to the card" }).click();

    // the card page knows the boss is defeated
    await expect(page.getByText("Boss defeated", { exact: true })).toBeVisible();
    // the library shows the rank of the paper
    await expect(page.locator(".rankpip.r3")).toBeVisible();
  });

  test("the Play page shows the level, the quests and the collection", async ({ page }) => {
    await signIn(page);
    await page.getByRole("tab", { name: "Play" }).click();
    await expect(page.getByRole("heading", { name: "Play", level: 1 })).toBeVisible();
    await expect(page.getByText("Level 1 of 6")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Explorer" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Quests of this week" })).toBeVisible();
    await expect(page.locator(".quest")).toHaveCount(3);
    await page.getByRole("radio", { name: "Cards" }).click();
    await expect(page.getByText("1 of 1 mastered")).toBeVisible();
    await expect(page.locator(".gcard.r3")).toContainText("AUTOMA");
  });

  test("buy a cap for the Duck with Sparks that the real work gave", async ({ page }) => {
    await signIn(page);
    await page.getByRole("tab", { name: "Play" }).click();
    await page.getByRole("radio", { name: "Shop" }).click();
    await page.getByRole("button", { name: "40" }).click();
    await page.getByRole("button", { name: "Wear", exact: true }).first().click();
    await expect(page.getByRole("button", { name: "Wearing" })).toBeVisible();
  });

  test("play a few weeks of the Semester Simulator", async ({ page }) => {
    await signIn(page);
    await page.getByRole("tab", { name: "Play" }).click();
    await page.getByRole("radio", { name: "Semester" }).click();
    await expect(page.getByText(/It gives no XP/)).toBeVisible();
    await page.getByRole("button", { name: /Start a semester/ }).click();
    await expect(page.getByText("5 action points")).toBeVisible();
    await page.getByRole("button", { name: /^Read papers/ }).click();
    await expect(page.getByText("4 action points")).toBeVisible();
    await page.getByRole("button", { name: /End the week/ }).click();
    // an event may come at the end of the week. The student answers it, and the next week starts.
    const event = page.locator(".event");
    if (await event.isVisible({ timeout: 3000 }).catch(() => false)) await event.getByRole("button").first().click();
    await expect(page.getByText("Week 2", { exact: false }).first()).toBeVisible();
    await expect(page.getByText(/\d action points/)).toBeVisible();
  });
});
