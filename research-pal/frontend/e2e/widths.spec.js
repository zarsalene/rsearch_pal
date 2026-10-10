// The same 13 pages at many screen widths, from a very small phone (320 px) to a laptop (1280 px).
// A page must never be wider than the screen. On a phone the layout viewport grows to fit a page that is too wide,
// so we compare with the width that we set (w), not with window.innerWidth.
import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PDF = path.join(path.dirname(fileURLToPath(import.meta.url)), ".generated", "a.pdf");
const WIDTHS = [320, 360, 412, 768, 1024, 1280];
const PAGES = ["Today", "Card", "Chat", "Search", "Review", "Journey", "To read", "Plan", "Glossary", "Write", "Links", "Thesis", "Settings"];

for (const w of WIDTHS) {
  test(`no page is wider than the screen at ${w} px`, async ({ browser }) => {
    test.setTimeout(150000);
    const phone = w <= 820;
    const ctx = await browser.newContext({ viewport: { width: w, height: 780 }, deviceScaleFactor: 2, isMobile: phone, hasTouch: phone });
    const page = await ctx.newPage();
    await page.goto("/");
    await page.getByLabel("Password").fill("e2e-password-123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("tab", { name: phone ? "More" : "Settings" })).toBeVisible();

    // one paper, so the card and the chat have real content
    if (phone) await page.getByRole("button", { name: "Open the library" }).click();
    const input = page.locator('input[type="file"]');
    await input.first().waitFor({ timeout: 2000 }).catch(() => page.getByRole("button", { name: "Add paper" }).click());
    await input.setInputFiles(PDF);
    await page.getByRole("button", { name: "Read the paper" }).click();
    await page.getByRole("tab", { name: "Card", exact: true }).click();
    await expect(page.getByRole("heading", { level: 1 })).toContainText("AUTOMA", { timeout: 40000 });

    const bad = [];
    for (const name of PAGES) {
      const tab = page.getByRole("tab", { name, exact: true });
      if (await tab.count()) await tab.click();
      else {
        await page.getByRole("tab", { name: "More" }).click();
        await page.getByRole("dialog", { name: "More" }).getByRole("button", { name: new RegExp(name) }).click();
      }
      await page.waitForTimeout(450);
      const over = await page.evaluate((width) => document.documentElement.scrollWidth - width, w);
      if (over > 1) bad.push(`${name} is ${over}px too wide`);
    }
    expect(bad, `at ${w} px`).toEqual([]);

    // on a phone, every tab of the bottom bar is inside the screen
    if (phone) {
      for (const name of ["Today", "Card", "Chat", "Search", "More"]) {
        const box = await page.getByRole("tab", { name, exact: true }).boundingBox();
        expect(box.x + box.width, `${name} tab is inside the screen`).toBeLessThanOrEqual(w + 1);
      }
    }
    await ctx.close();
  });
}
