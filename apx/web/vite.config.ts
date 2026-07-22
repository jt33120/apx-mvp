import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Static SPA build (AD-29): emits static assets to dist/, no Node runtime ships.
// All data access goes to the one API over HTTP; no server-rendering layer exists,
// so matter scope has exactly one place it can be wrong (the API), not two.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist" },
});
