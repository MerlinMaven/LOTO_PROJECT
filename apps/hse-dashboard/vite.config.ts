/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import fs from "node:fs";

const canonicalRoot = fs.realpathSync(process.cwd());

// The dashboard talks to the existing FastAPI backend.
// In dev, /api is proxied to the backend so there are no CORS concerns.
export default defineConfig({
  root: canonicalRoot,
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(canonicalRoot, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET ?? "http://localhost:8001",
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
