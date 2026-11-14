import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    host: true,
    port: 5173,
    proxy: { "/api": { target: process.env.API_PROXY ?? "http://localhost:8001", changeOrigin: true } },
  },
  test: { environment: "jsdom", globals: true, setupFiles: ["src/test-setup.ts"], exclude: ["e2e/**", "node_modules/**"] },
});
