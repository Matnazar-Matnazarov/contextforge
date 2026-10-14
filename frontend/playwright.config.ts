import { defineConfig } from "@playwright/test";

// Runs against the full Docker Compose stack (default http://localhost:8080).
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  retries: 0,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
    trace: "retain-on-failure",
    // Set E2E_CHROMIUM=/usr/bin/chromium to use a system browser instead of `playwright install`.
    launchOptions: process.env.E2E_CHROMIUM ? { executablePath: process.env.E2E_CHROMIUM } : {},
  },
});
