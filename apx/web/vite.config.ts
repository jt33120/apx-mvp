import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Static SPA (AD-29): all data access is HTTP to the one API (AD-14). In dev,
// proxy /api to the backend; in production the SPA is served as static files and
// talks to the same-origin API.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist" },
  server: { proxy: { "/api": "http://localhost:8000" } },
});
