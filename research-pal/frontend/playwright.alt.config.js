import { defineConfig, devices } from "@playwright/test";

// The tests start two servers: the backend with a fake AI (port 8011) and the frontend (port 5184).
// PYTHON: the Python that has the packages of the backend. In CI it is "python". On your computer, point it to your .venv.
const PYTHON = process.env.PYTHON || "python";
const API = "http://localhost:8011";
const APP = "http://localhost:5184";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1, // all tests use one server, so they run one after the other
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: { baseURL: APP, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `"${PYTHON}" scripts/fake_server.py --port 8011 --origin ${APP} --pdf-dir ../frontend/e2e/.generated`,
      cwd: "../backend",
      url: `${API}/api/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npm run dev -- --port 5184 --strictPort",
      // The tests use the one-password login, whatever is in frontend/.env (no email accounts).
      env: { VITE_API_URL: API, VITE_SUPABASE_URL: "", VITE_SUPABASE_ANON_KEY: "" },
      url: APP,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
