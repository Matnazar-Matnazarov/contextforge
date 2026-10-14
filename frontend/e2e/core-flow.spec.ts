import { expect, test } from "@playwright/test";

const email = `e2e-${Date.now()}@example.com`;
const password = "e2e-password-12345";

test("register -> create org -> upload -> indexed -> ask -> cited answer or explicit error", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page.getByRole("heading", { name: "Your organizations" })).toBeVisible();
  await page.getByLabel("Name").fill("E2E Org");
  await page.getByRole("button", { name: "Create", exact: true }).click();

  await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible();
  await page.getByLabel("Upload documents").setInputFiles({
    name: "vacation-policy.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Vacation\nFull-time employees receive 25 days of paid annual leave per year."),
  });
  await expect(page.getByText("Indexed")).toBeVisible({ timeout: 90_000 });

  await page.getByRole("link", { name: "Chat" }).click();
  await page.getByLabel("Your question").fill("How many days of annual leave do full-time employees get?");
  await page.getByRole("button", { name: "Send question" }).click();

  // With a valid GEMINI_API_KEY we expect a cited answer; without one the UI must show an explicit error, never a fake answer.
  const source = page.getByRole("button", { name: /S1.*vacation-policy\.md/ });
  const failure = page.getByRole("alert").filter({ hasText: /unavailable/i });
  await expect(source.or(failure)).toBeVisible({ timeout: 60_000 });
  if (await source.isVisible()) {
    await source.click();
    await expect(page.getByText("25 days of paid annual leave").first()).toBeVisible();
  }
});

test("unsupported file type is rejected client-side", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`e2e2-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Your organizations" })).toBeVisible();
  await page.getByLabel("Name").fill("Org Two");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await page.getByLabel("Upload documents").setInputFiles({ name: "malware.exe", mimeType: "application/octet-stream", buffer: Buffer.from("MZ") });
  await expect(page.getByText(/Unsupported file type/)).toBeVisible();
});
