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

  test("Simple mode shows the simple text, and a link shows the original", async ({ page }) => {
    await signIn(page);
    const method = page.locator("#f-method");
    await expect(method).toContainText("A hypothesis agent and a validation agent work together.");
    await page.getByRole("radio", { name: "Simple" }).click();
    await expect(method.locator(".answer")).toContainText("Simple: A hypothesis agent"); // the fake AI puts "Simple: " in front
    await expect(method.getByText("AI simplification")).toBeVisible();
    await expect(method.locator("blockquote").first()).toBeVisible(); // the quote and the page stay
    // the truth rule: a text that the AI cannot simplify safely keeps the original (the number 95.0 stays in the result)
    await expect(page.locator("#f-result .answer")).toContainText("95.0");
    await method.getByRole("button", { name: "Show the original" }).click();
    await expect(method.locator(".answer")).not.toContainText("Simple:");
    await page.reload(); // the browser remembers the choice
    await expect(page.getByRole("radio", { name: "Simple" })).toBeChecked();
    await page.getByRole("radio", { name: "Expert" }).click();
    await expect(method.locator(".answer")).not.toContainText("Simple:");
  });

  test("select a word, read the explanation, save it, find it in the glossary", async ({ page }) => {
    await signIn(page);
    // a word that the paper defines: the answer is a sentence of the PDF
    await selectWord(page, "#f-method .answer", "hypothesis");
    const box = page.getByRole("dialog", { name: "Meaning of hypothesis" });
    await expect(box).toContainText("From the paper");
    await expect(box).toContainText("A hypothesis is a short claim about a possible attack.");
    await expect(box.getByRole("button", { name: "p. 2" })).toBeVisible();
    await box.getByRole("button", { name: "Save to glossary" }).click();
    await expect(box.getByRole("button", { name: "In your glossary" })).toBeDisabled();
    await page.keyboard.press("Escape");
    await expect(box).toHaveCount(0);

    // a word that the paper does not define: the AI explains, and the label says so
    await selectWord(page, "#f-method .answer", "validation");
    const ai = page.getByRole("dialog", { name: "Meaning of validation" });
    await expect(ai).toContainText("AI explanation");
    await expect(ai).toContainText("It is not from the paper");
    await page.keyboard.press("Escape");

    await page.getByRole("tab", { name: "Glossary" }).click();
    const item = page.locator(".gloss-item", { hasText: "hypothesis" });
    await expect(item).toContainText("From the paper");
    await expect(item).toContainText("A hypothesis is a short claim about a possible attack.");
    await expect(page.locator(".gloss-item")).toHaveCount(1);
    await item.getByRole("button", { name: "Delete hypothesis" }).click();
    await expect(page.getByText("No word yet.")).toBeVisible();
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

// Select one word inside an element, like a student does with the mouse. Then the page gets the mouseup event.
async function selectWord(page, selector, word) {
  await page.locator(selector).first().scrollIntoViewIfNeeded(); // the student sees the word before the selection
  await page.evaluate(
    ({ selector, word }) => {
      const root = document.querySelector(selector);
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const i = node.textContent.indexOf(word);
        if (i < 0) continue;
        const range = document.createRange();
        range.setStart(node, i);
        range.setEnd(node, i + word.length);
        const sel = getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        root.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
        return;
      }
      throw new Error("The word is not in the page: " + word);
    },
    { selector, word },
  );
}
