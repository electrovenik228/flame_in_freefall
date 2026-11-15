import { expect, test } from "@playwright/test";

// Step 8 check. With E2E_ASSISTANT=live the five demo questions must return cited answers and an
// off-topic question must be declined. Without it (no Claude credit), the test still requires the
// status line within one second and a clear outcome: an answer or a plain notice.
const LIVE = process.env.E2E_ASSISTANT === "live";
const QUESTIONS = [
  "Which investigations matter most for a lunar habitat with 30% oxygen, and why?",
  "How do BASS-II and Saffire differ in sample size and flow?",
  "What has been tested on fire suppression in microgravity?",
  "Which records give test-by-test oxygen and pressure data for validating a model?",
  "What did the SAME experiments learn about smoke particles in microgravity?",
];

test("a status line appears within one second and the turn ends with an answer or a notice", async ({ page }) => {
  await page.goto("/assistant");
  await page.getByRole("button", { name: QUESTIONS[0] }).click();
  await expect(page.getByTestId("status")).toBeVisible({ timeout: 1000 });
  const answer = page.getByTestId("answer").last();
  await expect(answer.getByTestId("notice").or(answer.getByText("AI-generated"))).toBeVisible({ timeout: 90_000 });
  if (LIVE) await expect(answer.getByRole("button", { name: /^Source 1:/ })).toBeVisible();
});

test("five demo questions return cited answers and an off-topic question is declined", async ({ page }) => {
  test.skip(!LIVE, "needs Claude API credit: run with E2E_ASSISTANT=live");
  test.setTimeout(600_000);
  for (const question of QUESTIONS) {
    await page.goto("/assistant");
    await page.evaluate(() => sessionStorage.clear());
    await page.reload();
    await page.getByLabel("Your question").fill(question);
    await page.getByRole("button", { name: "Ask" }).click();
    await expect(page.getByTestId("status")).toBeVisible({ timeout: 1000 });
    const answer = page.getByTestId("answer").last();
    await expect(answer.getByText("AI-generated")).toBeVisible({ timeout: 120_000 });
    await expect(answer.getByRole("button", { name: /^Source 1:/ })).toBeVisible();
    await expect(answer.getByTestId("verified").or(answer.getByTestId("flagged"))).toBeVisible();
  }
  await page.getByLabel("Your question").fill("Write a poem about my cat and recommend a pizza topping.");
  await page.getByRole("button", { name: "Ask" }).click();
  const declined = page.getByTestId("answer").last();
  await expect(declined.getByText("AI-generated")).toBeVisible({ timeout: 60_000 });
  await expect(declined).toContainText(/combustion|fire/i);
  await expect(declined.getByRole("button", { name: /^Source \d+:/ })).toHaveCount(0);
});
