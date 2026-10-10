// The phone app: the layout of a phone screen (Redmi Note 13 Pro+ size), touch, and the sheets.
// Run: npm run test:mobile
import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PDF = path.join(path.dirname(fileURLToPath(import.meta.url)), ".generated", "a.pdf");
const PASSWORD = "e2e-password-123";
const PHONE = { viewport: { width: 393, height: 786 }, deviceScaleFactor: 2.75, isMobile: true, hasTouch: true };
const MORE = ["Review", "Journey", "To read", "Plan", "Glossary", "Write", "Links", "Thesis", "Settings"];

// Compare with the width of the screen, not with innerWidth: on a phone, innerWidth grows to fit a page that is too wide, so it would hide the fault.
const noSideScroll = (page) => page.evaluate((w) => document.documentElement.scrollWidth <= w + 1, PHONE.viewport.width);

async function start(browser, colorScheme) {
  const ctx = await browser.newContext({ ...PHONE, colorScheme });
  const page = await ctx.newPage();
  await page.goto("/");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("tab", { name: "More" })).toBeVisible();
  return { ctx, page };
}

// The upload form is open only while the library is empty. Otherwise the student taps "Add paper".
async function uploadOne(page) {
  await page.getByRole("button", { name: "Open the library" }).click();
  if (!(await page.locator('input[type="file"]').count())) await page.getByRole("button", { name: "Add paper" }).click();
  await page.locator('input[type="file"]').setInputFiles(PDF);
  await page.getByRole("button", { name: "Read the paper" }).click();
  await page.getByRole("tab", { name: "Card", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("AUTOMA");
}

for (const scheme of ["light", "dark"]) {
  test.describe(`phone, ${scheme}`, () => {
    test("bottom bar, sheets, drawer and every page", async ({ browser }) => {
      test.setTimeout(240000);
      const { ctx, page } = await start(browser, scheme);

      // the bottom bar: four tabs and "More". Each tab is big enough for a finger (44 px).
      await expect(page.getByRole("tab")).toHaveCount(5);
      for (const name of ["Today", "Card", "Chat", "Search", "More"]) {
        const box = await page.getByRole("tab", { name, exact: true }).boundingBox();
        expect(box.height, name).toBeGreaterThanOrEqual(44);
        expect(box.width, name).toBeGreaterThanOrEqual(60);
        expect(box.y + box.height, name + " is on the screen").toBeLessThanOrEqual(786);
      }
      // the theme choice is not in the top bar on a phone (it is in "More")
      await expect(page.locator(".bar .themeseg")).toHaveCount(0);

      // the library is a drawer. It starts closed. The menu button opens it and a tap outside closes it.
      const drawerRight = () => page.locator("#library").evaluate((el) => el.getBoundingClientRect().right);
      expect(await drawerRight()).toBeLessThanOrEqual(0);
      await page.getByRole("button", { name: "Open the library" }).click();
      await expect.poll(drawerRight).toBeGreaterThan(200);
      await page.locator(".scrim").click({ position: { x: 380, y: 300 } });
      await expect.poll(drawerRight).toBeLessThanOrEqual(0);

      // "More": the pages that do not fit. It opens and it closes with a tap outside.
      await page.getByRole("tab", { name: "More" }).click();
      const sheet = page.getByRole("dialog", { name: "More" });
      await expect(sheet).toBeVisible();
      for (const name of [...MORE, "Appearance"]) await expect(sheet.getByText(name, { exact: true })).toBeVisible();
      await page.locator(".sheet-scrim").click({ position: { x: 200, y: 60 } });
      await expect(sheet).toBeHidden();

      // each page opens, and no page is wider than the screen
      for (const name of ["Today", "Card", "Chat", "Search"]) {
        await page.getByRole("tab", { name, exact: true }).click();
        await page.waitForTimeout(450);
        expect(await noSideScroll(page), `${name} page has a side scroll`).toBe(true);
      }
      for (const name of MORE) {
        await page.getByRole("tab", { name: "More" }).click();
        await page.getByRole("dialog", { name: "More" }).getByRole("button", { name: new RegExp(name) }).click();
        await expect(page.getByRole("dialog", { name: "More" })).toBeHidden();
        await expect(page.getByRole("tab", { name: "More" })).toHaveAttribute("aria-selected", "true");
        await page.waitForTimeout(450);
        expect(await noSideScroll(page), `${name} page has a side scroll`).toBe(true);
      }
      await ctx.close();
    });

    test("a card: layout, chat input, touch word box", async ({ browser }) => {
      test.setTimeout(240000);
      const { ctx, page } = await start(browser, scheme);
      await uploadOne(page);

      // the Edit link never lies on the text of a field
      await expect(page.locator(".fbody .answer").first()).toBeVisible();
      const clash = await page.evaluate(() =>
        [...document.querySelectorAll(".fbody")].some((f) => {
          const e = f.querySelector(".edit-link")?.getBoundingClientRect();
          const a = f.querySelector(".answer");
          if (!e || !a) return false;
          // the text may be next to the link, but a line of the text must not run under it.
          // The link floats, so the box of the answer is as wide as the field. We measure the lines of the text (a range), not the box.
          const lines = document.createRange();
          lines.selectNodeContents(a);
          return [...lines.getClientRects()].some((r) => r.width > 1 && r.left < e.right - 1 && r.right > e.left + 1 && r.top < e.bottom - 1 && r.bottom > e.top + 1);
        }),
      );
      expect(clash).toBe(false);
      expect(await noSideScroll(page)).toBe(true);

      // a long press selects a word. On a phone there is no mouseup, so the box opens from the change of the selection.
      await page.evaluate(() => {
        const el = document.querySelector(".fbody .answer");
        const range = document.createRange();
        range.setStart(el.firstChild, 0);
        range.setEnd(el.firstChild, 8);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        document.dispatchEvent(new Event("selectionchange"));
      });
      const box = page.getByRole("dialog", { name: /Meaning of/ });
      await expect(box).toBeVisible({ timeout: 5000 });
      const b = await box.boundingBox();
      expect(b.x).toBeLessThanOrEqual(1); // the sheet is as wide as the screen
      expect(b.width).toBeGreaterThanOrEqual(390);
      await page.getByRole("button", { name: "Close the word box" }).click();
      await expect(box).toBeHidden();

      // the chat: the input sits just above the bottom bar
      await page.getByRole("tab", { name: "Chat" }).click();
      await page.waitForTimeout(600);
      const input = await page.getByPlaceholder(/Ask about/).boundingBox();
      const dock = await page.getByRole("tablist").boundingBox();
      expect(dock.y - (input.y + input.height)).toBeLessThan(40);
      expect(dock.y - (input.y + input.height)).toBeGreaterThanOrEqual(0);
      await ctx.close();
    });
  });
}
