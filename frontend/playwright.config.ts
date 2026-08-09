import { defineConfig, devices } from '@playwright/test'

// Smoke-test only (production-roadmap.md §8.2) — dev server, not a prod
// build/preview, since these two tests exist to catch "the app doesn't
// render at all" regressions, not to validate the production bundle (CI's
// `build` step in ci.yml already does that separately).
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:4321',
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'npm run dev -- --port 4321 --strictPort',
    url: 'http://localhost:4321',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
