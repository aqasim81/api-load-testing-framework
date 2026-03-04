import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "../src/loadforge/dashboard/static",
    emptyOutDir: true,
    chunkSizeWarningLimit: 600,
  },
  server: {
    proxy: {
      "/ws": {
        target: "ws://localhost:8089",
        ws: true,
      },
      "/api": {
        target: "http://localhost:8089",
      },
    },
  },
});
