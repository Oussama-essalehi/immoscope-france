/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative base path: the build works on Vercel, on GitHub Pages
// (https://<user>.github.io/<repo>/) and when served from any sub-folder.
export default defineConfig({
  base: "./",
  plugins: [react()],
  build: {
    outDir: "dist",
    sourcemap: false,
    // Recharts alone weighs ~530 kB minified (~160 kB gzipped) and is cached separately
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        // Separate, long-cached vendor chunks
        manualChunks: {
          react: ["react", "react-dom"],
          charts: ["recharts"],
          map: ["leaflet", "react-leaflet"],
        },
      },
    },
  },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
