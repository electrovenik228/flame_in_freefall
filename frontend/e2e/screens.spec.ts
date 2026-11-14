import { test } from "@playwright/test";

// Not a check: saves screenshots of each page in both themes for visual review (section 10.7).
const OUT = process.env.SCREENSHOT_DIR;
const PAGES: [string, string][] = (process.env.SCREENSHOT_PAGES ?? "investigations=/investigations")
  .split(",")
  .map((entry) => [entry.slice(0, entry.indexOf("=")), entry.slice(entry.indexOf("=") + 1)] as [string, string]);

for (const theme of ["dark", "light"]) {
  for (const [name, path] of PAGES) {
    test(`screenshot ${name} ${theme}`, async ({ page }) => {
      test.skip(!OUT, "set SCREENSHOT_DIR to save screenshots");
      await page.addInitScript((value) => localStorage.setItem("theme", value), theme);
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await page.screenshot({ path: `${OUT}/${name}-${theme}.png`, fullPage: true });
    });
  }
}
