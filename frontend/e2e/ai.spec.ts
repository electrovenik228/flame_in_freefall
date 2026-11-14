import { expect, test } from "@playwright/test";

// Step 6 output in the browser: a cited summary at two reading levels and quoted evidence.
test("an investigation shows a cited AI summary and its evidence", async ({ page }) => {
  await page.goto("/investigations/PSI-69");
  const summary = page.getByTestId("ai-summary");
  await expect(summary).toBeVisible();
  await expect(summary.getByText("AI-generated")).toBeVisible();
  await expect(summary.getByText("Not yet reviewed by an expert")).toBeVisible();

  const chip = summary.getByRole("button", { name: /^Source 1:/ });
  await chip.click();
  const source = page.getByRole("dialog", { name: "Source 1" });
  await expect(source).toContainText("PSI-69");
  await expect(source.getByRole("link", { name: "View on PSI" })).toHaveAttribute("href", /investigations\/PSI-69$/);
  await page.keyboard.press("Escape");
  await expect(source).toBeHidden();

  const plain = await summary.locator("p").first().innerText();
  await summary.getByRole("button", { name: "Expert" }).click();
  await expect(summary.locator("p").first()).not.toHaveText(plain);

  await page.getByText("Quoted evidence for the attributes read by AI").click();
  await expect(page.getByTestId("extraction-evidence").locator("blockquote").first()).toBeVisible();
});

test("AI-read attributes drive the catalogue filters", async ({ page }) => {
  await page.goto("/investigations?safety_function=detection");
  await expect(page.getByTestId("result-count")).toContainText(/^\d+ investigations, 1 filter applied/);
  await expect(page.getByRole("link", { name: "SAME", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "FLEX", exact: true })).toHaveCount(0);
});
