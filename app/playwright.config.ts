import { defineConfig, devices } from '@playwright/test';

const PORT = 4174;
export const TURN_TEST_URL = 'https://turn.e2e.invalid/api/v1/turn/credentials?apiKey=test';

export default defineConfig({
  testDir: 'e2e',
  fullyParallel: true,
  reporter: [['list']],
  use: {
    ...devices['Pixel 7'],
    baseURL: `http://localhost:${PORT}/`,
    // Fixture-Fragen werden per page.route geliefert; der Service Worker darf nicht dazwischenfunken
    serviceWorkers: 'block',
    locale: 'de-CH',
  },
  webServer: {
    command: `npm run build && npx vite preview --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}/`,
    reuseExistingServer: !process.env.CI,
    // TURN-Zugangsdaten: feste Test-URL, die e2e/netz.spec.ts per page.route beantwortet
    env: { VITE_TURN_CREDENTIALS_URL: TURN_TEST_URL },
    timeout: 120_000,
  },
});
