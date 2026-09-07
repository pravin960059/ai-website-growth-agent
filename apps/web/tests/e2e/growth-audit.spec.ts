import { expect, test } from "@playwright/test";

test("creates an audit and approves a generated recommendation", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Turn website evidence into approved momentum." })).toBeVisible();
  await page.getByTestId("website-url").fill("https://example.com");
  await page.getByTestId("project-name").fill(`Playwright workspace ${Date.now()}`);
  await page.getByTestId("growth-goal").fill("Validate the complete evidence and approval workflow.");
  await page.getByTestId("start-audit").click();

  await expect(page.getByText("Live audit stream")).toBeVisible();
  const auditState = page.locator(".state").first();
  await expect(auditState).toHaveText(/awaiting approval|completed/, { timeout: 75_000 });

  await expect(page.getByText(/FINDINGS \/ [0-9]+/)).toBeVisible();
  const approveButton = page.getByRole("button", { name: "Approve" }).first();
  await expect(approveButton).toBeVisible();
  await approveButton.click();

  await expect(page.getByText("approved").last()).toBeVisible();
  await expect(page.getByText("APPROVAL QUEUE / 00")).toBeVisible();
});
