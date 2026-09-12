import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

const repositoryRoot = resolve(import.meta.dirname, "../../..");

export default defineConfig({
  plugins: [
    {
      name: "claros-e2e-realtime-substitute",
      enforce: "pre",
      resolveId(source, importer) {
        if (
          source === "./realtime/loadOpenAIRealtime" &&
          importer?.endsWith("WorkspaceShell.tsx")
        ) {
          return resolve(
            import.meta.dirname,
            "openai-realtime-test-adapter.ts",
          );
        }
        return null;
      },
    },
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      "@": resolve(repositoryRoot, "src"),
    },
  },
  build: {
    emptyOutDir: true,
    manifest: true,
  },
});
