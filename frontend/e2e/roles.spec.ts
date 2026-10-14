import { expect, type Page, test } from "@playwright/test";

// Requires seeded data: `make seed` (users/orgs/documents from scripts/seed_demo.py).
const PASSWORD = "Demo-Pass-2026!";

async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: /sign in|log in/i }).click();
  await expect(page.getByRole("heading", { name: "Your organizations" })).toBeVisible();
}

async function openOrg(page: Page, name: string, section: "Chat" | "Documents" | "Members" = "Documents") {
  await page.getByRole("link", { name: new RegExp(name) }).click();
  await page.getByRole("link", { name: section, exact: true }).click();
}

test.describe("role matrix", () => {
  test("owner sees upload, delete and role controls", async ({ page }) => {
    await login(page, "owner@acme.test");
    await openOrg(page, "Acme Engineering");
    await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Delete rfc9110-http-semantics\.txt/ })).toBeVisible();
    await page.getByRole("link", { name: "Members" }).click();
    await expect(page.getByLabel("Role for member@acme.test")).toBeVisible();
    await expect(page.getByRole("button", { name: "Remove member@acme.test" })).toBeVisible();
  });

  test("admin can manage members but not remove the owner", async ({ page }) => {
    await login(page, "admin@acme.test");
    await openOrg(page, "Acme Engineering", "Members");
    await expect(page.getByRole("button", { name: "Remove member@acme.test" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Remove owner@acme.test" })).toHaveCount(0);
  });

  test("member can read and download but cannot delete or manage", async ({ page }) => {
    await login(page, "member@acme.test");
    await openOrg(page, "Acme Engineering");
    await expect(page.getByRole("link", { name: /Download rfc9110-http-semantics\.txt/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Delete / })).toHaveCount(0);
    await page.getByRole("link", { name: "Members" }).click();
    await expect(page.getByRole("button", { name: /Remove / })).toHaveCount(0);
  });

  test("outsider has no organizations and cannot open someone else's org", async ({ page }) => {
    await login(page, "outsider@demo.test");
    await expect(page.getByText(/Acme Engineering|Globex Library|Initech Docs/)).toHaveCount(0);
    const res = await page.request.get("/api/orgs/28ce6916-ce1a-4fb1-ad87-8a198e6003e6/documents/");
    expect(res.status()).toBe(404);
  });

  test("multi-org user sees the correct role in each organization", async ({ page }) => {
    await login(page, "multi@demo.test");
    const rows = page.getByRole("link", { name: /Acme Engineering|Globex Library|Initech Docs/ });
    await expect(rows).toHaveCount(3);
    await expect(page.getByRole("link", { name: /Initech Docs/ })).toContainText(/owner/i);
    await expect(page.getByRole("link", { name: /Globex Library/ })).toContainText(/admin/i);
    await expect(page.getByRole("link", { name: /Acme Engineering/ })).toContainText(/member/i);
  });

  test("wrong password is rejected", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("owner@acme.test");
    await page.getByLabel("Password").fill("not-the-password");
    await page.getByRole("button", { name: /sign in|log in/i }).click();
    await expect(page.getByRole("alert")).toBeVisible();
  });
});

test.describe("RAG over the seeded corpus", () => {
  test("cited answer from an RFC and download via citation", async ({ page }) => {
    await login(page, "owner@acme.test");
    await openOrg(page, "Acme Engineering", "Chat");
    await page.getByLabel("Your question").fill("What is the difference between the HTTP GET and POST methods?");
    await page.getByRole("button", { name: "Send question" }).click();
    const source = page.getByRole("button", { name: /S1.*rfc9110/ });
    await expect(source).toBeVisible({ timeout: 90_000 });
    await source.click();
    await expect(page.getByRole("complementary", { name: "Source" })).toBeVisible();
  });

  test("question outside the corpus gets an explicit insufficient-context answer", async ({ page }) => {
    await login(page, "owner@acme.test");
    await openOrg(page, "Acme Engineering", "Chat");
    await page.getByLabel("Your question").fill("What is the best recipe for chocolate cake with strawberries?");
    await page.getByRole("button", { name: "Send question" }).click();
    await expect(page.getByText(/not enough information|insufficient|couldn't find|do not contain/i).first()).toBeVisible({ timeout: 90_000 });
  });

  test("tenant isolation: Globex literature is not answerable from Initech", async ({ page }) => {
    await login(page, "multi@demo.test");
    await openOrg(page, "Initech Docs", "Chat");
    await page.getByLabel("Your question").fill("Who is Elizabeth Bennet in Pride and Prejudice?");
    await page.getByRole("button", { name: "Send question" }).click();
    await expect(page.getByRole("button", { name: /pride-and-prejudice/ })).toHaveCount(0, { timeout: 90_000 });
  });
});
