import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {baseURL: "http://127.0.0.1:13000", trace: "retain-on-failure"},
  webServer: process.argv.some(argument => argument.includes("money.spec.ts")) ? undefined : [
    {command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 18000", cwd: "../backend", url: "http://127.0.0.1:18000/health", reuseExistingServer: false, timeout: 60000},
    {command: "npm run dev -- --port 13000", url: "http://127.0.0.1:13000/auth", reuseExistingServer: false, timeout: 120000, env: {NEXT_PUBLIC_API_URL: "http://127.0.0.1:18000"}},
  ],
});
