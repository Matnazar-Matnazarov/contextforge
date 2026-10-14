import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, type Page, test } from "@playwright/test";

// Exercises every button on a throwaway org so seeded demo data is never touched.
const PASSWORD = "Demo-Pass-2026!";
const CORPUS = path.resolve(__dirname, "../../data/corpus/initech-docs");

async function registerAndCreateOrg(page: Page, tag: string) {
  const email = `ui-${tag}-${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Your organizations" })).toBeVisible();
  await page.getByLabel("Name").fill(`UI Org ${tag}`);
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible();
  return email;
}

test("documents: upload, index, download, re-index, delete", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("pageerror", (e) => consoleErrors.push(e.message));
  await registerAndCreateOrg(page, "docs");

  const name = "rust-book-ch10-03-lifetime-syntax.md";
  await page.getByLabel("Upload documents").setInputFiles({
    name,
    mimeType: "text/markdown",
    buffer: readFileSync(path.join(CORPUS, name)),
  });
  await expect(page.getByText("Indexed")).toBeVisible({ timeout: 90_000 });

  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: `Download ${name}` }).click();
  expect((await download).suggestedFilename()).toBe(name);

  await page.getByRole("button", { name: `Re-index ${name}` }).click();
  await expect(page.getByText("Indexed")).toBeVisible({ timeout: 90_000 });

  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: `Delete ${name}` }).click();
  await expect(page.getByRole("button", { name: `Delete ${name}` })).toHaveCount(0);
  expect(consoleErrors).toEqual([]);
});

test("members: add by email, change role, remove", async ({ page }) => {
  await registerAndCreateOrg(page, "members");
  await page.getByRole("link", { name: "Members", exact: true }).click();
  await page.getByLabel("Email").fill("outsider@demo.test");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByLabel("Role for outsider@demo.test")).toBeVisible();
  await page.getByLabel("Role for outsider@demo.test").selectOption("admin");
  await expect(page.getByLabel("Role for outsider@demo.test")).toHaveValue("admin");
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Remove outsider@demo.test" }).click();
  await expect(page.getByLabel("Role for outsider@demo.test")).toHaveCount(0);
  // unknown e-mail surfaces an error instead of silently succeeding
  await page.getByLabel("Email").fill("nobody-here@example.com");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: /./ }).first()).toBeVisible();
});

test("chat: ask, cite, open source panel, delete conversation, sign out", async ({ page }) => {
  await registerAndCreateOrg(page, "chat");
  const name = "rust-book-ch15-01-box.md";
  await page.getByLabel("Upload documents").setInputFiles({
    name,
    mimeType: "text/markdown",
    buffer: readFileSync(path.join(CORPUS, name)),
  });
  await expect(page.getByText("Indexed")).toBeVisible({ timeout: 90_000 });
  await page.getByRole("link", { name: "Chat", exact: true }).click();
  await page.getByLabel("Your question").fill("What is Box<T> used for in Rust?");
  await page.getByRole("button", { name: "Send question" }).click();
  const source = page.getByRole("button", { name: /S1.*rust-book-ch15-01-box\.md/ });
  await expect(source).toBeVisible({ timeout: 120_000 });
  await source.click();
  await expect(page.getByRole("complementary", { name: "Source" })).toContainText(/Box/);
  await page.getByRole("complementary", { name: "Source" }).getByRole("button", { name: "Close source" }).click();

  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: /Delete conversation/ }).first().click();
  await expect(page.getByText("No conversations yet.")).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/login/);
});
