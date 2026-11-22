import { defineConfig, devices } from '@playwright/test';

const PORT = 4173;
const isCI = Boolean(process.env.CI);

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  reporter: isCI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${String(PORT)}`,
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    // UI rule: every screen works at 375 px.
    { name: 'mobile-375', use: { ...devices['Desktop Chrome'], viewport: { width: 375, height: 812 } } },
  ],
  testIgnore: /\.shot\.ts$/,
  webServer: [
    {
      // The real API on its own port, so a running dev server doesn't interfere.
      command: 'uv run uvicorn trailcut_api.main:app --port 8001 --no-access-log',
      cwd: '../..',
      url: 'http://127.0.0.1:8001/health',
      reuseExistingServer: !isCI,
      timeout: 180_000,
      env: { TRAILCUT_RATE_LIMIT: '1000', TRAILCUT_ALLOWED_ORIGINS: `http://127.0.0.1:${String(PORT)}` },
    },
    {
      command: `pnpm build && pnpm preview --host 127.0.0.1 --port ${String(PORT)} --strictPort`,
      url: `http://127.0.0.1:${String(PORT)}`,
      reuseExistingServer: !isCI,
      timeout: 180_000,
      env: { TRAILCUT_API_PROXY: 'http://127.0.0.1:8001' },
    },
  ],
});
