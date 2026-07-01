import { defineConfig, devices } from "@playwright/test";

const webPort = process.env.WEB_PORT;

if (!webPort) {
  throw new Error("WEB_PORT is required. Run E2E tests through `npm run test:e2e` so codex-port can reserve the frontend port.");
}

const baseURL = `http://127.0.0.1:${webPort}`;

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: {
    timeout: 5_000
  },
  fullyParallel: false,
  reporter: "list",
  use: {
    baseURL,
    trace: "retain-on-failure"
  },
  webServer: {
    command: `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:65535 npm run dev -- --hostname 127.0.0.1 --port ${webPort}`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000
  },
  projects: [
    {
      name: "edge",
      use: {
        ...devices["Desktop Edge"],
        channel: "msedge"
      }
    }
  ]
});
