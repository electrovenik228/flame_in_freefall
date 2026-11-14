import { expect, test } from "@playwright/test";

// Step 7 check, acceptance scenario 1 (section 3): lunar habitat check, end to end.
test("lunar habitat: ranked list with score breakdown, then the cited summary of the top record", async ({ page }) => {
  await page.goto("/ranking?env=space-station");
  await page.getByRole("button", { name: "Lunar surface habitat and pressurized rover" }).click();
  await expect(page).toHaveURL(/env=lunar-habitat/);
  const summary = page.getByTestId("environment-summary");
  await expect(summary).toContainText("30% oxygen or more");
  await expect(summary).toContainText("70.3 kPa (10.2 psi) or less");
  await expect(summary).toContainText("1/6 g");

  const rows = page.getByTestId("ranking-row");
  await expect(rows).toHaveCount(23);
  const totals = (await page.getByTestId("total").allInnerTexts()).filter((text) => text !== "—").map(Number);
  expect(totals).toEqual([...totals].sort((a, b) => b - a));

  // Score breakdown: sub-scores add up to the total, each with an explanation and a PSI link.
  const top = rows.first();
  await top.getByRole("button", { name: "Breakdown" }).click();
  const breakdown = top.getByTestId("breakdown");
  await expect(breakdown.getByRole("rowheader", { name: "Atmosphere match" })).toBeVisible();
  await expect(breakdown).toContainText(/fall inside the target|The record states/);
  await expect(breakdown.getByRole("link", { name: /on PSI/ }).first()).toHaveAttribute("href", /psi\.nasa\.gov/);
  const points = (await breakdown.locator("tbody tr td:nth-child(4)").allInnerTexts()).filter((text) => text !== "—").map(Number);
  const total = Number(await top.getByTestId("total").innerText());
  expect(Math.abs(points.reduce((a, b) => a + b, 0) - total)).toBeLessThan(0.3);

  await expect(page.getByText("not a safety rating")).toBeVisible();
  await expect(page.getByText("PSI holds no partial-gravity data. Rankings for the Moon and Mars differ only")).toBeVisible();

  // Open the top record and read its cited summary.
  await top.getByRole("link").first().click();
  await expect(page).toHaveURL(/\/investigations\/PSI-\d+$/);
  await expect(page.getByTestId("ai-summary").getByRole("button", { name: /^Source 1:/ })).toBeVisible();
});

test("weights re-order the list in the browser without a request, and a low rank is explained", async ({ page }) => {
  await page.goto("/ranking?env=lunar-habitat");
  await expect(page.getByTestId("ranking-row")).toHaveCount(23);
  const names = async () => (await page.getByTestId("ranking-row").evaluateAll((rows) => rows.map((row) => row.querySelector("a")!.textContent))).join("|");
  const before = await names();
  const requests: string[] = [];
  page.on("request", (request) => request.url().includes("/api/") && requests.push(request.url()));

  const slider = page.getByRole("slider", { name: "Atmosphere match weight" });
  await slider.focus();
  for (let i = 0; i < 6; i += 1) await slider.press("ArrowLeft"); // 30 down to 0
  await expect(page).toHaveURL(/w_atmosphere=0/);
  expect(await names()).not.toBe(before);
  expect(requests).toEqual([]);

  const last = page.getByTestId("ranking-row").last();
  await last.getByRole("button", { name: /Why is this ranked/ }).click();
  await expect(last.getByTestId("why")).toContainText(/scores \d+%|No data for/);
  await page.getByRole("button", { name: "Reset" }).click();
  await expect(page).not.toHaveURL(/w_atmosphere/);
});

test("a custom atmosphere is ranked, including flow", async ({ page }) => {
  await page.goto("/ranking?env=custom");
  await expect(page.getByText("Enter an atmosphere")).toBeVisible();
  await page.getByLabel("Oxygen from, %").fill("20");
  await page.getByLabel("Oxygen to, %").fill("23");
  await page.getByLabel("Flow from, cm/s").fill("15");
  await page.getByLabel("Flow to, cm/s").fill("25");
  await page.getByRole("button", { name: "Rank for this atmosphere" }).click();
  await expect(page).toHaveURL(/oxygen_pct_min=20/);
  await expect(page.getByTestId("ranking-row")).toHaveCount(23);
  await expect(page.getByText("Flow match is not scored for this environment")).toHaveCount(0);
});

test("coverage map shows tested cells, the lunar window, gaps and the partial-gravity notice", async ({ page }) => {
  await page.goto("/coverage");
  await expect(page.getByTestId("chart").locator("canvas")).toBeVisible();
  await expect(page.getByTestId("coverage-caption")).toContainText("452 of 749 test runs are plotted");
  await expect(page.getByTestId("gap-lunar-habitat")).toContainText(/Tested: \d+ test runs inside/);
  await expect(page.getByTestId("gap-spacesuit")).toContainText("Untested: no test run inside this atmosphere");
  await expect(page.getByTestId("partial-gravity")).toContainText("No partial-gravity combustion data exists in PSI");
  await expect(page.getByTestId("partial-gravity")).toContainText("ACME E-FIELD Flames");
  await page.getByRole("button", { name: "Table" }).click();
  await expect(page.getByRole("columnheader", { name: "Test runs" })).toBeVisible();
  await page.getByRole("button", { name: "Flow speed" }).click();
  await expect(page.getByTestId("coverage-caption")).toContainText("11 of 749");
});
