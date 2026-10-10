// The phone app: the layout of a phone screen (Redmi Note 13 Pro+ size), touch, and the sheets.
// Run: npx playwright test e2e/mobile.spec.js
import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PDF = path.join(path.dirname(fileURLToPath(import.meta.url)), ".generated", "a.pdf");
const PHONE = { viewport: { width: 393, height: 786 }, deviceScaleFactor: 2.75, isMobile: true, hasTouch: true };

const noSideScroll = (page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
// Do two elements overlap on the screen?
const overlap = (page, a, b) =>
  page.evaluate(
    ([x, y]) => {
      const r1 = document.querySelector(x)?.getBoundingClientRect();
      const r2 = document.querySelector(y)?.getBoundingClientRect();
      if (!r1 || !r2) return false;
      return r1.left < r2.right && r1.right > r2.left && r1.top < r2.bottom && r1.bottom > r2.top;
    },
    [a, b],
  );

async function start(browser, colorScheme) {
  const ctx = await browser.newContext({ ...PHONE, colorScheme });
  const page = await ctx.newPage();
  await page.goto("/");
  await page.getByLabel("Password").fill("e2e-password-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("tab", { name: "More" })).toBeVisible();
  return { ctx, page };
}

for (const scheme of ["light", "dark"]) {
  test.describe(`phone, ${scheme}`, () => {
    test("bottom bar, sheets, drawer and pages", async ({ browser }) => {
      test.setTimeout(180000);
      const { ctx, page } = await start(browser, scheme);

      // the bottom bar: four tabs and "More". Each tab is big enough for a finger (44 px).
      const tabs = page.getByRole("tab");
      await expect(tabs).toHaveCount(5);
      for (const name of ["Card", "Chat", "Search", "Play", "More"]) {
        const box = await page.getByRole("tab", { name }).boundingBox();
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

      // "More": the pages that do not fit. It opens, it goes to the page, and it closes.
      await page.getByRole("tab", { name: "More" }).click();
      const sheet = page.getByRole("dialog", { name: "More" });
      await expect(sheet).toBeVisible();
      for (const name of ["Glossary", "Links", "Settings", "Appearance"]) await expect(sheet.getByText(name, { exact: true })).toBeVisible();
      await sheet.getByRole("button", { name: /Settings/ }).click();
      await expect(sheet).toBeHidden();
      await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
      await expect(page.getByRole("tab", { name: "More" })).toHaveAttribute("aria-selected", "true");

      // no page is wider than the screen
      for (const name of ["Card", "Chat", "Search", "Play", "More"]) {
        if (name === "More") {
          await page.getByRole("tab", { name }).click();
          await page.getByRole("dialog", { name: "More" }).getByRole("button", { name: /Links/ }).click();
        } else await page.getByRole("tab", { name }).click();
        await page.waitForTimeout(500);
        expect(await noSideScroll(page), `${name} page has a side scroll`).toBe(true);
      }

      // the chat: the input sits just above the bottom bar
      await page.getByRole("tab", { name: "Chat" }).click();
      await page.waitForTimeout(500);
      const input = await page.getByPlaceholder(/Ask about/).boundingBox();
      const dock = await page.getByRole("tablist").boundingBox();
      expect(dock.y - (input.y + input.height)).toBeLessThan(40);
      expect(dock.y - (input.y + input.height)).toBeGreaterThanOrEqual(0);
      await ctx.close();
    });

    test("a card: no overlap, reward message, touch word box", async ({ browser }) => {
      test.setTimeout(180000);
      const { ctx, page } = await start(browser, scheme);
      await page.getByRole("button", { name: "Open the library" }).click();
      // the upload form is open only while the library is empty. Otherwise the student taps "Add paper".
      if (!(await page.locator('input[type="file"]').count())) await page.getByRole("button", { name: "Add paper" }).click();
      await page.locator('input[type="file"]').setInputFiles(PDF);
      await page.getByRole("button", { name: "Read the paper", exact: true }).click();
      await expect(page.getByRole("heading", { level: 1 })).toContainText("AUTOMA");

      // the reward message is above the bottom bar and it does not cover the title
      const reward = page.locator(".reward").first();
      if (await reward.isVisible().catch(() => false)) {
        expect(await overlap(page, ".reward", ".card h1")).toBe(false);
        const r = await reward.boundingBox();
        expect(r.y + r.height).toBeLessThanOrEqual((await page.getByRole("tablist").boundingBox()).y);
      }

      // the Edit link never lies on the text of a field
      await expect(page.locator(".fbody .answer").first()).toBeVisible();
      const clash = await page.evaluate(() =>
        [...document.querySelectorAll(".fbody")].some((f) => {
          const e = f.querySelector(".edit-link")?.getBoundingClientRect();
          const a = f.querySelector(".answer")?.getBoundingClientRect();
          if (!e || !a) return false;
          // the text may be next to the link, but a line of the text must not run under it
          return [...f.querySelector(".answer").getClientRects()].some((r) => r.left < e.right && r.right > e.left && r.top < e.bottom && r.bottom > e.top);
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
      await ctx.close();
    });
  });
}
