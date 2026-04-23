/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { manualChunkName } from "./config/manualChunks";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    // The IFC viewer is already lazy-loaded, but its vendor chunks exceed Vite's default warning threshold.
    chunkSizeWarningLimit: 4000,
    rollupOptions: {
      output: {
        manualChunks: manualChunkName,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
});
