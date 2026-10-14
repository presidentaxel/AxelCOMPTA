import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 30_000,
  use: { baseURL: "http://localhost:3000", ...devices["Desktop Chrome"] },
  webServer: {
    command: "npm run dev -- --port 3000",
    url: "http://localhost:3000/connexion",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
