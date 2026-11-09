import { defineConfig, devices } from "@playwright/test";

// End-to-end tests run against the real API (apps/api, PostgreSQL) and this app, both started here
// unless already running. Before the first run: `docker compose up -d db` and
// `alembic upgrade head` (see apps/api/README.md). Set DATABASE_URL if your Postgres isn't on 5433.
//
// If you start the API yourself instead, give it ENABLE_DEV_ROUTES=true (tests reset data through
// /dev/reset) and RATE_LIMITS_ENABLED=false (the suite signs in far more often than the auth limit).
const python = process.platform === "win32" ? ".venv\\Scripts\\python" : ".venv/bin/python";

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false, // tests share one database and reset it
  workers: 1,
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] }, testMatch: /mobile\.spec\.ts/ },
  ],
  webServer: [
    {
      command: process.env.E2E_API_CMD ?? `${python} -m uvicorn app.main:app --port 8000`,
      cwd: "../api",
      // /ready, not /health: it waits for the database and current migrations.
      url: "http://localhost:8000/api/v1/ready",
      reuseExistingServer: true,
      // PAYPAL_MODE=mock: the e2e run never depends on real PayPal Sandbox credentials.
      env: { ...process.env, ENABLE_DEV_ROUTES: "true", RATE_LIMITS_ENABLED: "false", PAYPAL_MODE: "mock" } as Record<string, string>,
    },
    {
      command: "npm run dev",
      url: "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
