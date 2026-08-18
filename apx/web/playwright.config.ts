import { defineConfig, devices } from "@playwright/test";

/**
 * Browser tests against the composition a DEPLOYMENT actually has (story 7.8's harness).
 *
 * `apx/api/app.py` mounts the built SPA at `/` when `apx/web/dist` exists, so one process serves
 * the API and the client from the same origin. Driving a Vite dev server through its `/api` proxy
 * would exercise a composition no container uses — the sibling of the defect story 7.4 found, where
 * a path was only ever exercised in the configuration where it could not fail. So the harness
 * builds first and drives the real thing.
 *
 * The server seeds a throwaway SQLite database and data volume per run (`tests/e2e/serve.py`), with
 * AD-31's key and AD-35's head journal both pinned INTO that throwaway rather than disabled.
 */
const PORT = 8099;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,          // one seeded server, one matter: the specs share state by design
  forbidOnly: !!process.env.CI,
  retries: 0,                    // a flaky browser test that passes on retry is a test that lies
  reporter: process.env.CI ? "list" : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    locale: "fr-FR",             // the product speaks French; so does the harness
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "(cd apx/web && npm run build) && .venv/bin/python -m tests.e2e.serve",
    cwd: "../..",
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    stdout: "pipe",
    stderr: "pipe",
    env: { APX_E2E_PORT: String(PORT), PYTHONPATH: "." },
  },
});
