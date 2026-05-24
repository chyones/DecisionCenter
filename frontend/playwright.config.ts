import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for DecisionCenter frontend UI hardening (Phase 2C).
 *
 * Tests run against the Vite dev server so the dev-only RoleSwitcher is
 * available for role-scoped security assertions.
 * API calls are mocked via page.route() — no backend dependency.
 *
 * Phase 2C Slice 4: cross-browser matrix — Chromium, Firefox, WebKit.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5174',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
  webServer: {
    command: 'npm run dev -- --port 5174',
    url: 'http://localhost:5174',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
});
