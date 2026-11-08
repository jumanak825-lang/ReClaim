import { defineConfig, devices } from "@playwright/test";

// End-to-end tests run against the real stub API (apps/api) and this app, both started here
// unless already running. The API needs its venv: see apps/api/README.md.
const python = process.platform === "win32" ? ".venv\\Scripts\\python" : ".venv/bin/python";

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false, // tests share one in-memory API
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
      url: "http://localhost:8000/api/v1/health",
      reuseExistingServer: true,
    },
    {
      command: "npm run dev",
      url: "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
