import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const GENERATED = path.join(path.dirname(fileURLToPath(import.meta.url)), ".generated");
const PDF = path.join(GENERATED, "a.pdf");
const PDF_B = path.join(GENERATED, "b.pdf");
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
  test("the question helper: write, check, choose, make sub-questions, tag 2 papers, see the coverage", async ({ page }) => {
    await signIn(page);
    // a second paper. The first paper came from the test before.
    await page.getByRole("button", { name: "Add paper" }).click();
    await page.locator('input[type="file"]').setInputFiles(PDF_B);
    await page.getByRole("button", { name: "Read the paper" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Cooking pasta");

    // 1. write a vague question, 2. see the FINER check
    await page.getByRole("tab", { name: "Thesis" }).click();
    await page.getByLabel("Your question").fill("AI in health");
    await page.getByRole("button", { name: "Check my question" }).click();
    await expect(page.getByRole("list", { name: "FINER check" }).getByRole("listitem")).toHaveCount(5);
    await expect(page.getByText("Scope: too wide")).toBeVisible();
    await expect(page.getByText("AI opinion").first()).toBeVisible();
    // the AI saved nothing: the title bar has no question yet
    await expect(page.locator(".thesisbar")).not.toContainText("AI in health");

    // 3. choose a version, edit it, save it
    await page.getByRole("button", { name: "See narrower versions" }).click();
    await page.getByRole("radio", { name: /lung cancer/ }).check();
    await page.getByRole("button", { name: "Save as my main question" }).click();
    await expect(page.locator(".thesisbar")).toContainText("lung cancer");

    // 4. make the sub-questions from the AI suggestions
    await expect(page.getByRole("heading", { name: "Your sub-questions" })).toBeVisible();
    await page.getByRole("button", { name: "Suggest sub-questions" }).click();
    const suggested = page.getByRole("list", { name: "Suggested sub-questions" });
    await expect(suggested.getByText("AI suggestion")).toHaveCount(4);
    for (let left = 3; left >= 0; left--) {
      await suggested.getByRole("button", { name: "Add" }).first().click();
      await expect(suggested.getByRole("listitem")).toHaveCount(left);
    }
    await expect(page.getByLabel(/^Sub-question \d$/)).toHaveCount(4);
    await expect(page.getByText("No paper yet")).toHaveCount(4);

    // tag the 2 papers on their card pages
    await page.getByRole("tab", { name: "Card" }).click();
    await page.getByRole("button", { name: /AUTOMA/ }).click();
    const tags = page.getByRole("group", { name: "Sub-questions of this card" });
    await tags.getByRole("button", { name: "SQ1" }).click();
    await expect(tags.getByRole("button", { name: "SQ1" })).toHaveAttribute("aria-pressed", "true");
    await tags.getByRole("button", { name: "SQ2" }).click();
    await expect(tags.getByRole("button", { name: "SQ2" })).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: /Cooking pasta/ }).click();
    await tags.getByRole("button", { name: "SQ1" }).click();
    await expect(tags.getByRole("button", { name: "SQ1" })).toHaveAttribute("aria-pressed", "true");

    // the coverage: SQ1 has 2 papers, SQ2 has 1 paper, SQ3 and SQ4 have none
    await page.getByRole("tab", { name: "Thesis" }).click();
    await page.getByRole("button", { name: "Go to the sub-questions" }).click();
    await expect(page.getByRole("img", { name: "SQ1: 2 papers" })).toBeVisible();
    await expect(page.getByRole("img", { name: "SQ2: 1 paper" })).toBeVisible();
    await expect(page.getByRole("img", { name: "SQ3: No paper yet" })).toBeVisible();
  });

  test("the title bar edits the title, and the history keeps the old versions", async ({ page }) => {
    await signIn(page);
    await page.getByRole("button", { name: "Edit your thesis title and question" }).click();
    await page.getByLabel("Thesis title").fill("Agents for threat hunting");
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await expect(page.locator(".thesisbar")).toContainText("Agents for threat hunting");
    await page.getByRole("button", { name: "Edit your thesis title and question" }).click();
    await page.getByLabel("Thesis title").fill("Multi-agent threat hunting");
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await page.reload(); // the server keeps it
    await expect(page.locator(".thesisbar")).toContainText("Multi-agent threat hunting");
    await page.getByRole("tab", { name: "Thesis" }).click();
    const history = page.getByRole("region", { name: "History" });
    await expect(history).toContainText("Before: Agents for threat hunting");
    await expect(history).toContainText("Agents for threat hunting");
  });

  test("the thesis switch hides the title bar and the Thesis tab", async ({ page }) => {
    await signIn(page);
    await expect(page.getByRole("tab", { name: "Thesis" })).toBeVisible();
    await page.getByRole("tab", { name: "Settings" }).click();
    await page.getByRole("switch", { name: /Thesis direction/ }).click();
    await expect(page.getByRole("tab", { name: "Thesis" })).toHaveCount(0);
    await expect(page.locator(".thesisbar")).toHaveCount(0);
    await page.getByRole("switch", { name: /Thesis direction/ }).click();
    await expect(page.getByRole("tab", { name: "Thesis" })).toBeVisible();
    await expect(page.locator(".thesisbar")).toContainText("Multi-agent threat hunting"); // the data stayed
  });
});
