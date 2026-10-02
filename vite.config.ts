import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { resolve } from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": resolve(import.meta.dirname, "./src"),
    },
  },
  build: {
    manifest: true,
  },
  server: {
    port: 5173,
    allowedHosts: true,
    headers: {
      "Content-Security-Policy":
        "default-src 'self'; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data: blob:; connect-src 'self' ws: https://api.openai.com; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'self' https://replit.com https://*.replit.com",
    },
    proxy: {
      "/__mockup": {
        target: "http://127.0.0.1:23636",
        ws: true,
      },
      "/api": process.env.CLAROS_DEV_API_URL ?? "http://127.0.0.1:8787",
    },
  },
});
