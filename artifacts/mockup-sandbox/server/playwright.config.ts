import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "*.test.ts",
  fullyParallel: false,
  workers: 1,
  timeout: 20_000,
  outputDir: "/tmp/claros-demo-tests",
  reporter: "list",
  use: {
    launchOptions: { executablePath: "/repl/tools/bin/chromium", args: ["--no-sandbox", "--disable-dev-shm-usage"] },
  },
});