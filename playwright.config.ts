import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 180_000,
  expect: { timeout: 60_000 },
  preserveOutput: "always",
  fullyParallel: false,
  // PDFium/WASM initialization is intentionally serialized on the CI-sized
  // envelope so one worker cannot starve another during a cold start.
  workers: 1,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  outputDir: "output/playwright/application",
  globalTeardown: "./tests/e2e/support/global-teardown.ts",
  use: {
    baseURL: "http://127.0.0.1:18080",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "node tests/e2e/support/start-server.mjs",
    url: "http://127.0.0.1:18080/health",
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
