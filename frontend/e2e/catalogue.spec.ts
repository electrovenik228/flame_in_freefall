import { expect, test } from "@playwright/test";

// Step 5 check: browse, filter, open a record.
test("browse, filter and open an investigation", async ({ page }) => {
  await page.goto("/investigations");
  await expect(page.getByRole("heading", { level: 1, name: "Investigations" })).toBeVisible();
  await expect(page.getByTestId("result-count")).toContainText("23 investigations");
  await expect(page.getByTestId("investigation-card")).toHaveCount(23);

  await page.getByRole("button", { name: "Has test runs" }).click();
  await expect(page.getByTestId("result-count")).toContainText("6 investigations");
  await expect(page).toHaveURL(/has_test_runs=true/);

  await page.getByLabel("Fuel in test runs").fill("heptane");
  await expect(page.getByTestId("result-count")).toContainText("1 investigation,");
  await expect(page).toHaveURL(/fuel=heptane/);

  await page.getByRole("link", { name: "FLEX", exact: true }).click();
  await expect(page).toHaveURL(/\/investigations\/PSI-69$/);
  await expect(page.getByTestId("psi-id")).toHaveText("PSI-69");
  await expect(page.getByRole("link", { name: "View on PSI" })).toHaveAttribute(
    "href",
    "https://psi.nasa.gov/physci/repo/data/investigations/PSI-69",
  );
  await expect(page.getByRole("heading", { name: "Varied between tests" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "20CAL08" })).toBeVisible();
});

test("a shared link restores the filtered view, and the table view sorts", async ({ page }) => {
  await page.goto("/investigations?project=saffire&view=table&has_flow=true");
  await expect(page.getByTestId("result-count")).toContainText("3 investigations, 2 filters applied");
  await page.getByRole("button", { name: "Test runs", exact: true }).click(); // numbers sort high to low first
  await expect(page.locator("tbody tr").first()).toContainText("SAFFIRE-II");
});

test("a record without per-test data says so instead of showing empty charts", async ({ page }) => {
  await page.goto("/investigations/PSI-26");
  await expect(page.getByTestId("no-per-test-notice")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("BASS");
});

test("global search finds a fuel and an unknown record shows a clear message", async ({ page }) => {
  await page.goto("/investigations/PSI-9999");
  await expect(page.getByText("PSI-9999 is not in the catalogue")).toBeVisible();
  await page.getByLabel("Global search").fill("heptane");
  await page.getByRole("button", { name: /^Heptane \d+ runs/ }).click();
  await expect(page).toHaveURL(/fuel=Heptane/);
});
