import { expect, test, type BrowserContext } from '@playwright/test';
import { TURN_TEST_URL } from '../playwright.config';
import { fixturePool } from './helfer';

/**
 * Netz-Modus (WebRTC über Trystero). Echte Verbindungen lassen sich hier nicht testen; geprüft wird, dass die
 * TURN-Zugangsdaten geladen werden und die Diagnose den Zustand anzeigt. Relays werden blockiert, damit der Test
 * nicht vom Netz abhängt.
 */
async function vorbereiten(context: BrowserContext, turn: (route: import('@playwright/test').Route) => Promise<void>) {
  await context.route('**/questions.json', (route) => route.fulfill({ json: fixturePool() }));
  await context.routeWebSocket(/^wss:/, (ws) => ws.close());
  await context.route(TURN_TEST_URL, turn);
}

async function raumEroeffnen(context: BrowserContext) {
  const page = await context.newPage();
  await page.goto('./');
  await page.getByRole('button', { name: 'Mit mehreren Geräten spielen' }).click();
  await page.getByLabel('Dein Name').fill('Anna');
  await page.getByRole('button', { name: 'Raum eröffnen' }).click();
  await page.getByText(/^Verbindung:/).click();
  return page;
}

test('Netz: TURN-Zugangsdaten werden geladen, Diagnose zeigt den Zustand', async ({ context }) => {
  let anfragen = 0;
  await vorbereiten(context, async (route) => {
    anfragen++;
    await route.fulfill({
      json: [
        { urls: 'stun:stun.relay.metered.ca:80' },
        { urls: 'turn:global.relay.metered.ca:80', username: 'u', credential: 'p' },
      ],
    });
  });
  const page = await raumEroeffnen(context);
  const diagnose = page.locator('.diagnose');
  await expect(diagnose).toContainText(/TURN-Server\s*bereit/);
  await expect(diagnose).toContainText(/Relays\s*0 von 5 verbunden/);
  await expect(page.getByText('Verbindung: verbinde …')).toBeVisible();
  // Blockierte Relays meldet Trystero als relay-failed; die Diagnose zeigt das verständlich an
  await expect(diagnose).toContainText('Relays) sind nicht erreichbar');
  expect(anfragen).toBe(1);
});

test('Netz: ohne TURN-Zugangsdaten verbindet die App trotzdem (ohne TURN)', async ({ context }) => {
  await vorbereiten(context, (route) => route.fulfill({ status: 401, json: { error: 'invalid apiKey' } }));
  const page = await raumEroeffnen(context);
  const diagnose = page.locator('.diagnose');
  await expect(diagnose).toContainText(/TURN-Server\s*Zugangsdaten nicht ladbar/);
  await expect(diagnose).toContainText('von 5 verbunden');
});
