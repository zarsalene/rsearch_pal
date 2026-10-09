import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const GENERATED = path.join(path.dirname(fileURLToPath(import.meta.url)), ".generated");
const PDF = path.join(GENERATED, "a.pdf");
const PDF_B = path.join(GENERATED, "b.pdf");
const PASSWORD = "e2e-password-123";

// Today is the home page. Most tests need the cards, so signIn opens the Card tab, unless home is true.
async function signIn(page, home = false) {
  await page.goto("/");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("tab", { name: "Settings" })).toBeVisible();
  if (!home) await page.getByRole("tab", { name: "Card", exact: true }).click();
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

  test("Today is the first page: goal, next action, focus timer, win", async ({ page }) => {
    await signIn(page, true);
    await expect(page.getByRole("tab", { name: "Today", exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("region", { name: "Next best action" })).toBeVisible();
    await expect(page.locator(".next-text")).not.toBeEmpty();
    await expect(page.getByRole("group", { name: "Coming soon" })).toContainText("Streak");

    // goals: add one, check it
    await page.getByLabel("New goal").fill("Read 1 paper");
    await page.getByRole("button", { name: "Add", exact: true }).click();
    await page.getByRole("checkbox", { name: "Read 1 paper" }).click(); // it changes after the server answers
    await expect(page.getByLabel("1 of 1 done")).toBeVisible();

    // focus timer: start, see the time go, stop. The server counts the minutes.
    await page.getByLabel("What do you do?").fill("Read the method");
    await page.getByRole("button", { name: "Start 25 minutes" }).click();
    await expect(page.getByRole("timer")).toContainText(/2[45]:\d\d/);
    await expect(page.getByRole("timer")).toContainText("Focus");
    await page.getByRole("button", { name: "Stop", exact: true }).click();
    await expect(page.getByRole("status").filter({ hasText: "You focused for 0 minutes" })).toBeVisible(); // a very short test session
    await expect(page.getByRole("button", { name: "Start 25 minutes" })).toBeVisible();

    // the win of the day, and the past wins
    await page.getByLabel("Your win of the day").fill("I started the focus timer.");
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await expect(page.locator(".win-today")).toContainText("I started the focus timer.");
    await page.getByRole("button", { name: "Show my past wins" }).click();
    await expect(page.getByText("No past win yet")).toBeVisible();

    // the big button opens the right place
    await page.reload();
    await expect(page.getByRole("region", { name: "Next best action" })).toBeVisible();
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
    await page.getByRole("tab", { name: "Card", exact: true }).click(); // after a reload the home page is Today
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

  test("Understand: explain the paper, see the colors, read it like I am 12, do the quiz", async ({ page }) => {
    await signIn(page);
    await page.getByRole("tab", { name: "Understand" }).click();

    // A1: the Feynman check. The fake AI marks 2 claims correct. The server marks the number 95.0 wrong (it is not in the PDF).
    await page.getByLabel("Your explanation").fill("The system uses a hypothesis agent. It reaches a precision of 91.4 percent. The recall is 95.0 percent. It also cooks pasta.");
    await page.getByRole("button", { name: "Check my explanation" }).click();
    await expect(page.getByLabel("Score 67 of 100")).toBeVisible();
    await expect(page.locator(".claim.mark-correct:not(.legend)")).toHaveCount(2);
    await expect(page.locator(".claim.mark-wrong:not(.legend)")).toHaveCount(1);
    await expect(page.locator(".claim.mark-not_in_paper:not(.legend)")).toHaveCount(1);
    await expect(page.getByText(/Good start. 1 point is missing/)).toBeVisible();
    await page.getByRole("button", { name: /The recall is 95.0 percent/ }).click();
    await expect(page.getByRole("region", { name: "Proof for the selected claim" })).toContainText("The number 95.0 is not in the paper.");
    await page.getByRole("button", { name: /The system uses a hypothesis agent/ }).click();
    await expect(page.getByRole("region", { name: "Proof for the selected claim" }).getByRole("button", { name: "p. 2" })).toBeVisible();
    await expect(page.getByText("Points that you did not mention")).toBeVisible();
    await expect(page.getByText("Progress: 67")).toBeVisible(); // the history shows the attempt

    // A2: like I am 12. The example and the analogy have the label "AI suggestion".
    await page.getByRole("tab", { name: "Like I am 12" }).click();
    await page.getByRole("button", { name: "Explain it like I am 12" }).click();
    await expect(page.locator(".eli-result .answer").first()).toContainText("Simple: ");
    await expect(page.locator(".eli-result").getByText("AI suggestion")).toHaveCount(2);
    await expect(page.getByText("The paper calls this: hypothesis agent.")).toBeVisible();

    // A5: the quiz. One question at a time. A wrong answer shows the correct quote and page.
    await page.getByRole("tab", { name: "Quiz me" }).click();
    await page.getByRole("button", { name: "Make new questions" }).click();
    await expect(page.getByText("Question 1 of 2")).toBeVisible();
    await expect(page.getByRole("heading", { name: "What does the hypothesis agent read?" })).toBeVisible();
    await page.getByLabel("Your answer").fill("It reads the Sysmon logs.");
    await page.getByRole("button", { name: "Check my answer" }).click();
    await expect(page.locator(".quizres .badge")).toHaveText("Correct");
    await page.getByRole("button", { name: "Next question" }).click();
    await page.getByLabel("Your answer").fill("I do not remember.");
    await page.getByRole("button", { name: "Check my answer" }).click();
    await expect(page.locator(".quizres .badge")).toHaveText("Wrong");
    await expect(page.locator(".quizres")).toContainText("The OpTC dataset.");
    await expect(page.locator(".quizres").getByRole("button", { name: "p. 3" })).toBeVisible();
    await page.getByRole("button", { name: "See the result" }).click();
    await expect(page.getByText("1 of 2 answers were correct.")).toBeVisible();
  });

  test("Game: a Feynman pass gives points, and the Journey page shows them", async ({ page }) => {
    await signIn(page);
    await page.getByRole("tab", { name: "Understand" }).click();
    await page.getByLabel("Your explanation").fill("Analysts spend many hours on manual log review. The system uses a hypothesis agent and a validation agent. It reaches a precision of 91.4 percent and a recall of 84.2 percent.");
    await page.getByRole("button", { name: "Check my explanation" }).click();
    await expect(page.getByLabel("Score 100 of 100")).toBeVisible();
    await expect(page.locator(".xpnote")).toContainText("+25 points"); // the server gave the points. The page cannot.

    await page.getByRole("tab", { name: "Journey" }).click();
    const level = page.getByRole("region", { name: "Level", exact: true });
    await expect(level).toContainText("Explorer");
    // earlier tests gave some points too (a quiz answer, a win). The Feynman pass gave 25 of them.
    const points = Number(((await level.textContent()).match(/(\d+) points/) || [])[1]);
    expect(points).toBeGreaterThanOrEqual(25);
    await expect(level).toContainText("1 of 3 Feynman checks passed"); // the way to Reader
    await expect(page.getByRole("region", { name: "Badges" })).toContainText("First Feynman pass");
    await expect(page.getByRole("region", { name: "Where your points came from" })).toContainText("A Feynman check passed");
    await expect(page.getByRole("region", { name: "Streak" })).toContainText("1 day");
    await expect(page.getByRole("region", { name: "Records" })).toContainText("There is no ranking");

    // an own reward
    await page.getByLabel("My reward").fill("A coffee");
    await page.getByLabel("Condition of the reward").fill("xp:20");
    await page.getByRole("button", { name: "Add", exact: true }).click();
    await expect(page.getByRole("button", { name: /You earned it. Claim it/ })).toBeVisible();

    // the Today page shows the level and the streak in its boxes
    await page.getByRole("tab", { name: "Today", exact: true }).click();
    await expect(page.getByLabel("Level", { exact: true })).toContainText(/Explorer · \d+ points/);
    await expect(page.getByLabel("Streak", { exact: true })).toContainText("1 day");
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
