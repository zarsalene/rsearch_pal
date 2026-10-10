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

    // the first upload of a new server also starts the vector store (a slow first start on a slow PC), so this one waits longer
    await expect(page.getByRole("heading", { level: 1 })).toContainText("AUTOMA: Multi-agent threat hunting", { timeout: 60000 });
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
    await page.getByLabel("Explain it to Duck").fill("The system uses a hypothesis agent. It reaches a precision of 91.4 percent. The recall is 95.0 percent. It also cooks pasta.");
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
    await page.getByLabel("Explain it to Duck").fill("Analysts spend many hours on manual log review. The system uses a hypothesis agent and a validation agent. It reaches a precision of 91.4 percent and a recall of 84.2 percent.");
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
    // the avatar: the items of the level, the next item, and a button to hide it
    const avatar = page.getByRole("region", { name: "Avatar", exact: true });
    await expect(avatar).toContainText("Items: Backpack.");
    await expect(avatar).toContainText("At the next level you get: Glasses and a book.");
    await expect(avatar.getByRole("img")).toBeVisible();
    await avatar.getByRole("button", { name: "Hide avatar" }).click();
    await expect(avatar).toContainText("The avatar is hidden.");
    await avatar.getByRole("button", { name: "Show avatar" }).click();

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

  test("Review: water the plants, the count goes down, the garden is fresh; the map shows the road", async ({ page }) => {
    await signIn(page, true);
    const tile = page.locator(".soon[aria-label=\"Review\"]"); // the box on the Today page
    await expect(tile).toContainText(/\d+ items? due/);
    const due = Number((await tile.textContent()).match(/(\d+) items? due/)[1]);
    expect(due).toBeGreaterThanOrEqual(3); // the main idea of the card and the 2 quiz questions
    await tile.getByRole("button", { name: "Water your plants" }).click();
    await expect(page.getByRole("heading", { name: "Review", level: 1 })).toBeVisible();
    await expect(page.getByLabel("Knowledge Garden").getByRole("button").first()).toHaveClass(/plant ok/);
    await page.getByRole("button", { name: /^Review \d+ due/ }).click();

    for (let n = 1; n <= due; n++) {
      await expect(page.getByText(`Item ${n} of ${due}`)).toBeVisible();
      await expect(page.getByRole("button", { name: "Good", exact: true })).toHaveCount(0); // the student thinks first
      await page.getByRole("button", { name: "Show answer" }).click();
      await page.getByRole("button", { name: "Good", exact: true }).click();
    }
    await expect(page.getByRole("status")).toContainText(`You reviewed ${due} items.`);
    await page.getByRole("button", { name: "Back to the garden" }).click();
    await expect(page.getByRole("button", { name: "Nothing is due today" })).toBeDisabled();
    await expect(page.getByLabel("Knowledge Garden").getByRole("button").first()).toHaveClass(/plant fresh/);

    await page.getByRole("tab", { name: "Today", exact: true }).click();
    await expect(page.locator(".soon[aria-label=\"Review\"]")).toContainText("0 items due");

    // the Expedition map
    await page.getByRole("tab", { name: "Journey" }).click();
    const map = page.getByRole("region", { name: "PhD Expedition map" });
    await expect(map.getByRole("group", { name: /Map of the PhD road/ })).toBeVisible();
    await map.locator("g.region").first().click(); // Question Peak
    await expect(page.getByRole("region", { name: /Question Peak: what to do/ })).toContainText("First step");
    await map.locator("g.region").nth(2).click(); // Method Workshop: it fills with the decisions of the journal
    await expect(page.getByRole("region", { name: /Method Workshop: what to do/ })).toContainText("Plan tab");
    for (const name of ["Method Workshop", "Data Mines", "Writing Coast", "Defense Castle"]) {
      await expect(map.getByRole("button", { name: new RegExp(name + ", 0%, Not started") })).toBeVisible(); // these features come in later sprints
    }
  });

  test("Quests: choose 2 of 3, a third is refused, a drop has no penalty; mark a boss; the Duck can be hidden", async ({ page }) => {
    await signIn(page, true);
    const block = page.getByRole("region", { name: "Quests of this week" });
    await expect(block.getByRole("heading", { name: "Choose your quests" })).toBeVisible();
    await expect(block.locator("li.quest")).toHaveCount(3);
    const choose = block.getByRole("button", { name: "Choose", exact: true });
    await choose.first().click();
    await expect(block.locator("li.quest.chosen")).toHaveCount(1);
    await block.getByRole("button", { name: "Choose", exact: true }).first().click();
    await expect(block.locator("li.quest.chosen")).toHaveCount(2);
    await expect(block.getByRole("button", { name: "Choose", exact: true })).toBeDisabled(); // the third is refused: 2 each week
    await block.getByRole("button", { name: "Drop it" }).first().click(); // a drop has no penalty
    await expect(block.locator("li.quest.chosen")).toHaveCount(1);
    await expect(block.getByRole("button", { name: "Choose", exact: true }).first()).toBeEnabled();

    // a boss: the button on the card, the crown in the library, the line in the Journey page
    await page.getByRole("tab", { name: "Card", exact: true }).click();
    await page.getByRole("button", { name: "Mark as boss" }).click();
    await expect(page.getByRole("button", { name: /Boss paper/ })).toBeVisible();
    await expect(page.locator(".pitem.sel .crown")).toBeVisible();
    await page.getByRole("tab", { name: "Journey" }).click();
    const bosses = page.getByRole("region", { name: "Bosses" });
    await expect(bosses).toContainText("AUTOMA");
    await expect(bosses).toContainText("both need 80%");
    await expect(page.getByRole("region", { name: "Quest log" })).toBeVisible();
    await page.getByRole("tab", { name: "Card", exact: true }).click();
    await page.getByRole("button", { name: /Boss paper/ }).click(); // take the mark away
    await expect(page.getByRole("button", { name: "Mark as boss" })).toBeVisible();

    // the Duck: it says the text of the field, shows a message, and can be hidden
    await page.getByRole("tab", { name: "Understand" }).click();
    await expect(page.locator("aside.duck")).toContainText(/Duck/);
    await page.getByLabel("Explain it to Duck").fill("The system uses a hypothesis agent and a validation agent together.");
    await page.getByRole("button", { name: "Check my explanation" }).click();
    await expect(page.getByLabel("Score", { exact: false }).first()).toBeVisible();
    await expect(page.locator(".duckmsg")).not.toBeEmpty();
    await page.getByRole("button", { name: "Hide Duck" }).click();
    await expect(page.locator("aside.duck")).toHaveCount(0);
    await expect(page.getByLabel("Your explanation")).toBeVisible();
    await page.getByRole("tab", { name: "Settings" }).click(); // put the Duck back for the other tests
    await page.getByRole("switch", { name: /Duck companion/ }).click();
    await expect(page.getByRole("switch", { name: /Duck companion/ })).toBeChecked();
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

  test("Write: metadata, BibTeX, outline, a section with 2 quotes and their citations, autosave, Markdown export", async ({ page }) => {
  await signIn(page);
  // the metadata: the server read them from the PDF and checked them
  await page.locator(".pitem", { hasText: "AUTOMA" }).click();
  await page.getByRole("button", { name: "Fill from the PDF" }).click();
  await expect(page.getByRole("region", { name: "Metadata of the paper" })).toContainText("Smith, Jane; Wei, Li");
  await expect(page.getByRole("region", { name: "Metadata of the paper" })).toContainText("2024");
  // BibTeX export
  const bib = page.waitForEvent("download");
  await page.getByRole("button", { name: "BibTeX" }).click();
  expect((await bib).suggestedFilename()).toBe("research-pal.bib");

  // the outline, one section for each sub-question
  await page.getByRole("tab", { name: "Write" }).click();
  await page.getByRole("button", { name: "Make the outline" }).click();
  const sections = page.locator(".outline .osec");
  await expect(sections.first()).toBeVisible();
  const n = await sections.count();
  let found = false;
  for (let i = 0; i < n && !found; i++) {
    await sections.nth(i).click();
    found = (await page.getByRole("button", { name: /Insert quote/ }).count()) >= 2;
  }
  expect(found).toBe(true); // a section has cards with checked quotes

  await page.getByLabel("Your text").fill("Two papers study this question.\n");
  // wait for the save that has both quotes. The older "Saved" note of the first save is not enough: it made this test flaky.
  const saved = page.waitForResponse((r) => r.url().includes("/api/review-doc/sections/") && r.request().method() === "PUT" && (r.request().postData() || "").split("\\n> ").length > 2);
  await page.getByRole("button", { name: /Insert quote/ }).nth(0).click();
  await page.getByRole("button", { name: /Insert quote/ }).nth(1).click();
  const area = page.getByLabel("Your text");
  const value = await area.inputValue();
  expect(value.split("\n").filter((l) => l.startsWith("> "))).toHaveLength(2);
  expect(value).toMatch(/\(Smith & Wei, 2024, p\. \d\)/); // the citation with the page
  await saved; // autosave

  await page.reload(); // the text is not lost
  await page.getByRole("tab", { name: "Write" }).click();
  await page.locator(".outline .osec", { hasText: /\d+ words/ }).first().click();
  const kept = await page.locator(".outline li.sel .osec").count();
  expect(kept).toBe(1);

  // export Markdown with the citations and the references
  const md = page.waitForEvent("download");
  await page.getByRole("button", { name: /Export Markdown/ }).click();
  const file = await (await md).path();
  const text = (await import("node:fs")).readFileSync(file, "utf8");
  expect(text).toContain("# Literature review");
  expect(text).toContain("Two papers study this question.");
  expect(text).toMatch(/\(Smith & Wei, 2024, p\. \d\)/);
  expect(text).toContain("## References");
  expect(text).toContain("Smith, J., & Wei, L. (2024).");
});

  test("Gaps: a true point keeps its quotes, a gap is an AI opinion, Use this gap adds a section; Coach marks a claim without a citation; Quality needs a checked quote", async ({ page }) => {
    await signIn(page, true);
    await page.getByRole("tab", { name: "Write" }).click();
    await page.getByRole("tab", { name: "Gaps", exact: true }).click();
    const gaps = page.getByRole("region", { name: "Gap finder" });
    await gaps.getByRole("button", { name: "Find gaps" }).click();
    await expect(gaps).toContainText("Both papers describe a method.");
    await expect(gaps).toContainText("page 2"); // the checked quotes of the point
    await expect(gaps).not.toContainText("Both papers use the same data."); // its second quote was false: the server dropped the point
    await expect(gaps).toContainText("Nobody tested the systems on encrypted traffic.");
    await expect(gaps).toContainText("AI opinion");
    await gaps.getByRole("button", { name: /Confirm the gap/ }).click();
    await expect(gaps).toContainText("You confirmed it");
    await gaps.getByRole("button", { name: /Use this gap/ }).click();
    await page.getByRole("tablist", { name: "Part of the review" }).getByRole("tab", { name: "Write" }).click();
    await expect(page.locator(".outline .osec", { hasText: "Nobody tested the systems on encrypted traffic." })).toBeVisible();

    // the coach: a claim with a number and no citation is marked. The coach gives no new text.
    await page.locator(".outline .osec", { hasText: "Nobody tested the systems" }).click();
    await page.getByLabel("Your text").fill("The system reaches 91.4 percent precision on the logs.\n");
    await page.getByRole("button", { name: "Coach", exact: true }).click();
    const panel = page.getByRole("region", { name: "Coach comments" });
    await expect(panel).toContainText("It has no citation");
    await expect(panel).toContainText("The coach gives no new text");

    // the quality check on a card: an answer has a checked quote, or it is "Unclear"
    await page.getByRole("tab", { name: "Card", exact: true }).click();
    await page.getByText("AUTOMA: Multi-agent threat hunting").first().click();
    await page.getByRole("tab", { name: "Quality" }).click();
    await page.getByRole("button", { name: "Run the quality check" }).click();
    const q = page.getByRole("region", { name: "Quality check" });
    await expect(q).toContainText("AI opinion");
    await expect(q).toContainText("We present AUTOMA");
    await expect(q).toContainText("No checked quote");
    await q.getByRole("button", { name: "Confirm this check" }).click();
    await expect(q).toContainText("You confirmed this check.");
  });

  test("Duck Island: play Quote Hunt, see the sources, win coins, buy an item and place it; play gives no points", async ({ page }) => {
    await signIn(page, true);
    await page.getByRole("tab", { name: "Journey" }).click();
    const level = page.getByRole("region", { name: "Level", exact: true });
    const points = async () => Number(((await level.textContent()).match(/(\d+) points/) || [])[1]);
    const before = await points();
    await page.getByRole("button", { name: "Open Duck Island" }).click();
    const island = page.getByRole("region", { name: "Duck Island" });
    await expect(island).toContainText("Play gives no points and no levels");
    await island.getByRole("button", { name: /Go to Quote Hunt/ }).click();
    const round = page.getByRole("region", { name: "Quote Hunt" });
    const result = page.getByRole("region", { name: "Round result" });
    await expect(round).toContainText("question 1 of");
    const total = Number(((await round.textContent()).match(/question 1 of (\d+)/) || [])[1]);
    for (let i = 1; i <= total; i++) {
      await expect(round).toContainText(`question ${i} of ${total}`); // wait for the next question before the next click
      await round.locator(".playoptions button").first().click();
    }
    await expect(result).toContainText("right");
    await expect(result).toContainText("page"); // each source shows its page and its quote
    await result.getByRole("button", { name: "Back to the island" }).click();
    // the shop: the coins of work and play pay for a flower (5 coins)
    await island.getByRole("button", { name: /Go to the Shop/ }).click();
    await island.getByRole("button", { name: "Buy Flower for 5 coins" }).click();
    await expect(island.getByText("You have it.")).toBeVisible();
    await island.getByRole("button", { name: "Close the shop" }).click();
    await island.getByRole("button", { name: "Decorate" }).click();
    await island.getByRole("button", { name: "Place at the Duck" }).click();
    expect(await points()).toBe(before); // play and shop gave no points
  });

  test("Plan: a milestone, weekly tasks from the AI, a weekly review, a journal decision that fills the map", async ({ page }) => {
    await signIn(page, true);
    await page.getByRole("tab", { name: "Plan" }).click();
    const timeline = page.getByRole("region", { name: "Timeline" });
    await timeline.getByLabel("New milestone", { exact: true }).fill("First paper");
    await timeline.getByLabel("Due date of the new milestone").fill("2027-01-15");
    await timeline.getByRole("button", { name: "Add milestone" }).click();
    await expect(timeline.getByRole("img", { name: /Timeline from today/ })).toBeVisible();
    await timeline.getByRole("button", { name: "Suggest weekly tasks" }).click();
    await expect(timeline.getByText("AI suggestion").first()).toBeVisible(); // the AI text has its label
    await expect(timeline.getByLabel("Task: Read two papers about the method.", { exact: true })).toBeVisible();
    await timeline.getByRole("checkbox", { name: "Done: Read two papers about the method." }).click();
    await expect(timeline.getByText(/1 of 4 tasks done/)).toBeVisible();
    // the student changes an AI task: the label goes away
    const task = timeline.getByLabel("Task: Tag the papers to your sub-questions.", { exact: true });
    await task.fill("Tag my papers to the sub-questions.");
    await task.blur();
    await expect(timeline.getByLabel("Task: Tag my papers to the sub-questions.", { exact: true })).toBeVisible();
    await expect(timeline.getByText("AI suggestion")).toHaveCount(3);

    // the weekly review: points one time
    const review = page.getByRole("region", { name: "Weekly review", exact: true });
    await review.getByLabel("What did you do this week?").fill("Read two papers.");
    await review.getByLabel("Good", { exact: true }).click();
    await review.getByRole("button", { name: "Save the review" }).click();
    await expect(review).toContainText("+15 points");
    await review.getByRole("button", { name: "Update the review" }).click();
    await expect(review.getByRole("status")).toHaveText(/^\s*Saved\.\s*$/); // a second save gives no points

    // the journal: a decision fills the Method Workshop
    const journal = page.getByRole("region", { name: "Research journal" });
    await journal.getByLabel("Kind").selectOption("decision");
    await journal.getByLabel("Journal entry").fill("I use a validation agent to check each hypothesis.");
    await journal.getByRole("button", { name: "Save the entry" }).click();
    await expect(journal).toContainText("I use a validation agent");
    await page.getByRole("tab", { name: "Journey" }).click();
    await expect(page.getByRole("button", { name: /Method Workshop, 10%, Growing/ })).toBeVisible();
  });

  test("Find papers: add by DOI (and not twice), import a BibTeX file, rate the To read list", async ({ page }) => {
    await signIn(page, true);
    const library = page.getByRole("complementary", { name: "Library" });
    await expect(library.getByText("AUTOMA: Multi-agent threat hunting").first()).toBeVisible(); // the library has loaded
    const field = library.getByLabel("Add by DOI, link or title");
    if (!(await field.isVisible())) await library.getByRole("button", { name: "Add paper", exact: true }).click();
    await expect(field).toBeVisible();

    // a paper that has a free PDF: the app reads it
    const before = await library.locator("li").count();
    await library.getByLabel("Add by DOI, link or title").fill("https://doi.org/10.9999/closed.1");
    await library.getByRole("button", { name: "Add the paper" }).click();
    await expect(page.getByText("The app is reading the paper.")).toBeVisible();
    // the app shows the message first and then loads the list again, so wait for the new item before we count
    await expect(library.locator("li")).toHaveCount(before + 1);

    // the same paper is not added twice
    const count = before + 1;
    await library.getByLabel("Add by DOI, link or title").fill("https://doi.org/10.9999/closed.1");
    await library.getByRole("button", { name: "Add the paper" }).click();
    await expect(page.getByText("This paper is in your library already.")).toBeVisible();
    expect(await library.locator("li").count()).toBe(count);

    // import a BibTeX file without PDFs: the entries go to the To read list
    await page.getByRole("tab", { name: "Settings" }).click();
    const bib = "@article{a,\n title={Deep learning finds lung cancer in X-ray images},\n author={Doe, John},\n year={2022},\n abstract={We train deep learning models to find lung cancer in X-ray images.}\n}\n@article{b,\n title={Cooking pasta with tomatoes at home},\n author={Rossi, Mario},\n year={2020},\n abstract={How to cook pasta with tomato sauce and basil for dinner.}\n}\n";
    await page.locator('input[accept*=".bib"]').setInputFiles({ name: "lib.bib", mimeType: "text/plain", buffer: Buffer.from(bib) });
    await page.getByRole("button", { name: "Import", exact: true }).click();
    await expect(page.getByText("0 added to the library, 2 added to the To read list, 0 skipped")).toBeVisible();

    // the To read list: the best fit is first, with a reason. A not useful item goes away.
    await page.getByRole("tab", { name: "To read" }).click();
    const list = page.getByRole("region", { name: "To read" });
    await expect(list.locator(".toreaditem")).toHaveCount(2);
    await expect(list.locator(".toreaditem").first()).toContainText("Deep learning finds lung cancer in X-ray images");
    await expect(list.locator(".toreaditem").first()).toContainText("Fits");
    await list.locator(".toreaditem").nth(1).getByRole("button", { name: "Not useful" }).click();
    await expect(list.locator(".toreaditem")).toHaveCount(1);

    // suggestions: from the references and the citations of the library papers. Each has a tag and a true reason.
    await list.getByRole("button", { name: "Suggest papers now" }).click();
    await expect(page.getByText(/new suggestions? in your To read list/)).toBeVisible();
    await expect(list.getByText("Suggested").first()).toBeVisible();
    await expect(list.getByText(/Cited by \d+ of your papers|Cites \d+ of your papers/).first()).toBeVisible();
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
