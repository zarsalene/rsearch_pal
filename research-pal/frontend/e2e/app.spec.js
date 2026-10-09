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

test.describe.serial("Research Pal", () => {
  test("a wrong password is refused", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Password").fill("not-the-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("alert")).toContainText("Wrong password");
  });

  test("login, upload a PDF, see the card with its checked quotes", async ({ page }) => {
    await signIn(page);
    await page.locator('input[type="file"]').setInputFiles(PDF);
    await page.getByRole("button", { name: "Read the paper" }).click();

    await expect(page.getByRole("heading", { level: 1 })).toContainText("AUTOMA: Multi-agent threat hunting");
    // a true claim shows its quote and its page
    const problem = page.locator("#f-problem");
    await expect(problem).toContainText("Analysts spend many hours on manual log review");
    await expect(problem.getByRole("button", { name: "p. 1" })).toBeVisible();
    // the truth rule in the browser: the fake AI invents a quote for the limitation. The card hides the claim.
    const limitation = page.locator("#f-limitation");
    await expect(limitation).toContainText("The AI gave no proof for this claim, so the card hides it");
    await expect(limitation).toContainText("Quote not found in the PDF");
    await expect(limitation.locator(".answer").first()).not.toContainText("The system fails on encrypted traffic");
  });

  test("a feature switch hides the Chat tab and brings it back", async ({ page }) => {
    await signIn(page);
    await expect(page.getByRole("tab", { name: "Chat" })).toBeVisible();
    await page.getByRole("tab", { name: "Settings" }).click();
    const chat = page.getByRole("switch", { name: /Chat/ });
    await expect(chat).toBeChecked();
    await chat.click(); // the switch changes after the server answers, so we do not use uncheck()
    await expect(page.getByRole("tab", { name: "Chat" })).toHaveCount(0);
    await page.reload(); // the server keeps the choice
    await page.getByRole("tab", { name: "Settings" }).click();
    await expect(page.getByRole("switch", { name: /Chat/ })).not.toBeChecked();
    await page.getByRole("switch", { name: /Chat/ }).click();
    await expect(page.getByRole("tab", { name: "Chat" })).toBeVisible();
  });
});
