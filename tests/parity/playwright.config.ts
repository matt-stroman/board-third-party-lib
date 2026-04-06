import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: ["*.spec.ts"],
  reporter: [["list"], ["html", { outputFolder: "playwright-report/parity", open: "never" }]],
  snapshotDir: "./__snapshots__",
  use: {
    baseURL: process.env.PARITY_BASE_URL ?? "http://127.0.0.1:4173",
    ignoreHTTPSErrors: true,
    viewport: { width: 1440, height: 960 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure"
  }
});
