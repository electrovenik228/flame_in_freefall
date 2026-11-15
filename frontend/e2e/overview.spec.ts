import { expect, test } from "@playwright/test";

test("overview shows counts, safety tiles, the incident timeline and reaches an answer in three clicks", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("fire safety");
  await expect(page.getByLabel("Key counts")).toContainText("23");
  await expect(page.getByLabel("Key counts")).toContainText("749");
  await expect(page.getByTestId("timeline").getByRole("listitem")).toHaveCount(3);
  await expect(page.getByTestId("timeline").getByRole("link", { name: "Source: NASA" }).first()).toHaveAttribute("href", /nasa\.gov/);
  await expect(page.getByTestId("tile-detection")).toContainText(/\d+ investigations/);

  // Click 1: ranking for a lunar habitat. Click 2: the top record. The cited summary is the answer.
  await page.getByRole("link", { name: "Rank for a lunar habitat" }).click();
  await expect(page.getByTestId("ranking-row")).toHaveCount(23);
  await page.getByTestId("ranking-row").first().getByRole("link").first().click();
  await expect(page.getByTestId("ai-summary")).toBeVisible();
});

test("safety tile opens the filtered catalogue, and About explains the rubric and the AI", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("tile-suppression").click();
  await expect(page).toHaveURL(/safety_function=suppression/);
  await page.goto("/about");
  await expect(page.getByRole("cell", { name: "Atmosphere match" })).toBeVisible();
  await expect(page.getByText("does not replace NASA flammability standards or testing").first()).toBeVisible();
  await expect(page.getByText("A program checks that every quote appears word for word")).toBeVisible();
  await expect(page.getByText("stored for 30 days under an anonymous session ID")).toBeVisible();
});

test("the theme toggle switches and is remembered", async ({ page }) => {
  await page.goto("/");
  const html = page.locator("html");
  const before = await html.getAttribute("class");
  await page.getByRole("button", { name: /Switch to (light|dark) theme/ }).click();
  await expect(html).not.toHaveAttribute("class", before ?? "");
  const after = await html.getAttribute("class");
  await page.reload();
  await expect(html).toHaveAttribute("class", after ?? "");
});
