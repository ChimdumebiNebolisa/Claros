import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globals: true,
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
    exclude: ["output/**", "node_modules/**"],
    pool: "threads",
    maxWorkers: 1,
  },
});
