import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

const frontendDirectory = __dirname;
const backendDirectory = path.resolve(frontendDirectory, "../backend");
const backendPython = path.resolve(
  backendDirectory,
  ".venv/Scripts/python.exe",
);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `"${backendPython}" -m uvicorn subtitle_forge_api.app:app --host 127.0.0.1 --port 8000`,
      cwd: backendDirectory,
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npm.cmd run dev -- --hostname 127.0.0.1 --port 3000",
      cwd: frontendDirectory,
      url: "http://127.0.0.1:3000",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
  projects: [
    {
      name: "desktop-chromium",
      use: { ...devices["Desktop Chrome"], channel: "chrome" },
    },
    {
      name: "mobile-chromium",
      use: {
        ...devices["Desktop Chrome"],
        channel: "chrome",
        viewport: { width: 375, height: 812 },
      },
    },
  ],
});
