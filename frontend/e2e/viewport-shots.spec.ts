import { test } from "@playwright/test";

// Not a check: viewport-sized screenshots for visual review.
const OUT = process.env.SCREENSHOT_DIR;
const PAGES: [string, string][] = (process.env.VIEWPORT_PAGES ?? "").split(",").filter(Boolean)
  .map((entry) => [entry.slice(0, entry.indexOf("=")), entry.slice(entry.indexOf("=") + 1)] as [string, string]);

for (const [name, path] of PAGES) {
  test(`viewport ${name}`, async ({ page }) => {
    test.skip(!OUT, "set SCREENSHOT_DIR to save screenshots");
    await page.addInitScript(() => localStorage.setItem("theme", "dark"));
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(400);
    await page.screenshot({ path: `${OUT}/${name}-viewport.png` });
  });
}
