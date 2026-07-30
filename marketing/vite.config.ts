import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: path.resolve(__dirname, "../frontend"),
    emptyOutDir: false,
    rollupOptions: {
      input: path.resolve(__dirname, "landing.html"),
      output: {
        entryFileNames: "landing-app.js",
        chunkFileNames: "landing-[name].js",
        assetFileNames: (assetInfo) => {
          const name = assetInfo.name ?? ""
          if (name.endsWith(".css")) {
            return "styles/landing.css"
          }
          if (name.endsWith(".woff2")) {
            return "fonts/[name][extname]"
          }
          return "landing-assets/[name]-[hash][extname]"
        },
      },
    },
  },
})
