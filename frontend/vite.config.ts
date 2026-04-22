/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

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
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) {
            return undefined;
          }

          if (id.includes("@thatopen/components")) {
            return "ifc-open-components";
          }

          if (id.includes("@thatopen/fragments")) {
            return "ifc-fragments";
          }

          if (id.includes("web-ifc")) {
            return "ifc-web-ifc";
          }

          if (id.includes("three") || id.includes("camera-controls")) {
            return "ifc-three";
          }

          if (id.includes("react-konva") || id.includes("/konva/")) {
            return "canvas-editor";
          }

          if (
            id.includes("/node_modules/react/") ||
            id.includes("/node_modules/react-dom/") ||
            id.includes("/node_modules/react-router/") ||
            id.includes("/node_modules/react-router-dom/")
          ) {
            return "app-react";
          }

          if (id.includes("@tanstack/react-query")) {
            return "app-query";
          }

          return undefined;
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
});
