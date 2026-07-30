import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    ssr: path.resolve(__dirname, "src/entry-server.tsx"),
    outDir: path.resolve(__dirname, ".ssr"),
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "entry-server.js",
      },
    },
  },
})
