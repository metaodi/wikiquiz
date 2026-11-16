import { expect, test, type BrowserContext, type Page } from '@playwright/test';
import { beantworten, fixturePool, frageOeffnen, warteAufFrage, weiter } from './helfer';

/**
 * Mehrere Geräte = mehrere Tabs im selben Browser-Kontext (BroadcastChannel).
 * Uhr und Fragen-Route gelten für den ganzen Kontext: Alle Tabs teilen dieselbe Fake-Zeit.
 */
async function vorbereiten(context: BrowserContext) {
  await context.clock.install({ time: new Date('2026-11-15T10:00:00Z') });
  await context.clock.pauseAt(new Date('2026-11-15T10:00:01Z'));
  await context.route('**/questions.json', (route) => route.fulfill({ json: fixturePool() }));
}

async function geraetOeffnen(context: BrowserContext): Promise<Page> {
  const page = await context.newPage();
  await page.goto('./?mehrgeraete');
  await page.getByRole('button', { name: 'Mit mehreren Geräten spielen' }).click();
  return page;
}

async function raumEroeffnen(context: BrowserContext, name: string) {
  const host = await geraetOeffnen(context);
  await host.getByLabel('Dein Name').fill(name);
  await host.getByRole('button', { name: 'Raum eröffnen' }).click();
  const code = (await host.getByLabel('Raumcode').textContent())!.trim();
  expect(code).toMatch(/^[A-Z0-9]{4}$/);
  return { host, code };
}

async function beitreten(context: BrowserContext, code: string, name: string) {
  const gast = await geraetOeffnen(context);
  await gast.getByLabel('Dein Name').fill(name);
  await gast.getByLabel('Raumcode').fill(code.toLowerCase());
  await gast.getByRole('button', { name: 'Beitreten' }).click();
  return gast;
}

const spielerImRaum = (page: Page) => page.getByRole('list', { name: 'Spieler im Raum' });

test('zwei Geräte: Lobby, Züge reihum, Zuschauen, Neuladen, zurück zum Raum, verlassen', async ({ context }) => {
  await vorbereiten(context);
  const { host, code } = await raumEroeffnen(context, 'Anna');
  const gast = await beitreten(context, code, 'Ben');

  // Lobby
  await expect(gast.getByText('Warte, bis Anna das Spiel startet …')).toBeVisible();
  await expect(spielerImRaum(host)).toContainText('Ben');
  await expect(spielerImRaum(gast)).toContainText('Anna');
  await host.getByRole('radio', { name: '5', exact: true }).click();
  await host.getByRole('button', { name: 'Spiel starten' }).click();

  // Zug 1: Anna (Host) ist dran, Ben schaut zu
  await expect(host.getByRole('heading', { name: /Du bist dran,\s*Anna/ })).toBeVisible();
  await expect(gast.getByRole('heading', { name: 'Anna ist dran' })).toBeVisible();
  await host.getByRole('button', { name: 'Bereit' }).click();
  await expect(gast.getByRole('heading', { name: 'Anna wählt eine Kategorie' })).toBeVisible();
  const frage = await frageOeffnen(host, 'geografie');
  // Der Zuschauer sieht dieselbe Frage, kann aber nicht antworten
  await expect(gast.getByRole('heading', { level: 1 })).toHaveText(frage);
  await expect(gast.locator('.antwort').first()).toBeDisabled();
  expect(await beantworten(host, { typ: 'richtig', nachMs: 3000 })).toBe(82);
  await expect(gast.getByRole('heading', { name: 'Richtig!' })).toBeVisible();
  await expect(gast.getByText('Warte auf Anna …')).toBeVisible();
  await expect(gast.getByRole('button', { name: 'Weiter' })).toHaveCount(0);
  await weiter(host);

  // Zug 2: Ben (Gast) ist dran, Anna schaut zu
  await expect(gast.getByRole('heading', { name: /Du bist dran,\s*Ben/ })).toBeVisible();
  await expect(host.getByRole('heading', { name: 'Ben ist dran' })).toBeVisible();
  await gast.getByRole('button', { name: 'Bereit' }).click();
  await gast.getByRole('button', { name: /Kunst, Musik/ }).click();
  await warteAufFrage(gast);
  await expect(host.locator('.antwort').first()).toBeDisabled();
  expect(await beantworten(gast, { typ: 'richtig' })).toBe(100);
  await expect(host.getByText('Warte auf Ben …')).toBeVisible();

  // Gast lädt neu: Er wird wiedererkannt und sieht denselben Stand
  await gast.reload();
  await expect(gast.getByRole('heading', { name: 'Richtig!' })).toBeVisible();
  await weiter(gast);

  // Zwischenstand: nur der Host startet die nächste Runde
  await expect(gast.getByRole('heading', { name: 'Zwischenstand' })).toBeVisible();
  await expect(gast.getByText('Warte auf Anna …')).toBeVisible();
  await host.getByRole('button', { name: 'Runde 2 starten' }).click();
  await expect(host.getByRole('heading', { name: /Du bist dran,\s*Anna/ })).toBeVisible();
  await expect(gast.getByRole('heading', { name: 'Anna ist dran' })).toBeVisible();

  // Host lädt neu: Das Spiel geht weiter
  await host.reload();
  await expect(host.getByRole('heading', { name: /Du bist dran,\s*Anna/ })).toBeVisible();
  await expect(host.getByText('Runde 2 von 5')).toBeVisible();

  // Host beendet das Spiel → alle zurück in den Raum
  host.once('dialog', (d) => d.accept());
  await host.getByRole('button', { name: 'Bereit' }).click();
  await host.getByRole('button', { name: 'Spiel beenden' }).click();
  await expect(host.getByRole('button', { name: 'Spiel starten' })).toBeVisible();
  await expect(gast.getByText('Warte, bis Anna das Spiel startet …')).toBeVisible();

  // Gast verlässt den Raum
  await gast.getByRole('button', { name: 'Raum verlassen' }).click();
  await expect(gast.getByRole('button', { name: 'Mit mehreren Geräten spielen' })).toBeVisible();
  await expect(spielerImRaum(host)).not.toContainText('Ben');
});

test('Beitritt abgelehnt bei vergebenem Namen; Host schliesst den Raum', async ({ context }) => {
  await vorbereiten(context);
  const { host, code } = await raumEroeffnen(context, 'Anna');

  const doppelt = await beitreten(context, code, 'anna');
  await expect(doppelt.getByRole('alert')).toHaveText('Dieser Name ist im Raum schon vergeben.');
  await expect(spielerImRaum(host).getByRole('listitem')).toHaveCount(1);

  const gast = await beitreten(context, code, 'Cleo');
  await expect(gast.getByText('Warte, bis Anna das Spiel startet …')).toBeVisible();
  await host.getByRole('button', { name: 'Raum schliessen' }).click();
  await expect(gast.getByRole('alert')).toHaveText('Der Raum wurde geschlossen.');
  await expect(host.getByRole('button', { name: 'Mit mehreren Geräten spielen' })).toBeVisible();
});

test('Mehrere Geräte: ohne ?mehrgeraete nicht sichtbar; bei 320 px kein horizontales Scrollen', async ({
  context,
}) => {
  await vorbereiten(context);
  const normal = await context.newPage();
  await normal.goto('./');
  await expect(normal.getByRole('button', { name: 'Spiel starten' })).toBeVisible();
  await expect(normal.getByRole('button', { name: 'Mit mehreren Geräten spielen' })).toHaveCount(0);

  const { host } = await raumEroeffnen(context, 'Ein ziemlich langer Name');
  await host.setViewportSize({ width: 320, height: 640 });
  const pruefen = async () => {
    expect(await host.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
    const zuKlein = await host.evaluate(() =>
      [...document.querySelectorAll('button, a, input')]
        .map((el) => el.getBoundingClientRect())
        .filter((r) => r.width > 0 && (r.height < 47.5 || r.width < 47.5)).length,
    );
    expect(zuKlein).toBe(0);
  };
  await pruefen();
  await host.getByRole('button', { name: 'Raum schliessen' }).click();
  await host.getByRole('button', { name: 'Mit mehreren Geräten spielen' }).click();
  await pruefen();
  expect(await host.locator('body').innerText()).not.toContain('ß');
});
