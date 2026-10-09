import { defineConfig, devices } from "@playwright/test";

// The tests start two servers: the backend with a fake AI (port 8001) and the frontend (port 5174).
// PYTHON: the Python that has the packages of the backend. In CI it is "python". On your computer, point it to your .venv.
const PYTHON = process.env.PYTHON || "python";
const API = "http://localhost:8001";
const APP = "http://localhost:5174";

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
      command: `"${PYTHON}" scripts/fake_server.py --port 8001 --origin ${APP} --pdf-dir ../frontend/e2e/.generated`,
      cwd: "../backend",
      url: `${API}/api/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npm run dev -- --port 5174 --strictPort",
      env: { VITE_API_URL: API },
      url: APP,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
