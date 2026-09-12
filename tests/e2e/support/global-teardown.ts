import { rm } from "node:fs/promises";
import { resolve, sep } from "node:path";

export default async function globalTeardown() {
  const outputRoot = resolve("output", "playwright");
  const storagePath = resolve(outputRoot, "e2e-runtime-storage");
  if (!storagePath.startsWith(`${outputRoot}${sep}`)) {
    throw new Error("Refusing to clean E2E storage outside output/playwright");
  }
  await rm(storagePath, { recursive: true, force: true });
}
