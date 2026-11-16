import { expect, test, type BrowserContext, type Page } from '@playwright/test';
import { beantworten, fixturePool, frageOeffnen, KAT_NAME, warteAufFrage, weiter } from './helfer';

/**
 * Mehrere Geräte = mehrere Tabs im selben Browser-Kontext: `?kanal=tabs` verbindet sie über BroadcastChannel statt
 * WebRTC (kein Netzwerk nötig, Raum-Logik identisch).
 * Uhr und Fragen-Route gelten für den ganzen Kontext: Alle Tabs teilen dieselbe Fake-Zeit.
 */
async function vorbereiten(context: BrowserContext, pool = fixturePool()) {
  await context.clock.install({ time: new Date('2026-11-15T10:00:00Z') });
  await context.clock.pauseAt(new Date('2026-11-15T10:00:01Z'));
  await context.route('**/questions.json', (route) => route.fulfill({ json: pool }));
}

async function geraetOeffnen(context: BrowserContext): Promise<Page> {
  const page = await context.newPage();
  await page.goto('./?kanal=tabs');
  await page.getByRole('button', { name: 'Mit mehreren Geräten spielen' }).click();
  return page;
}

type Stufe = 'Leicht' | 'Mittel' | 'Schwer';

async function raumEroeffnen(context: BrowserContext, name: string, stufe?: Stufe) {
  const host = await geraetOeffnen(context);
  await host.getByLabel('Dein Name').fill(name);
  if (stufe) await host.getByRole('radiogroup', { name: 'Schwierigkeit', exact: true }).getByRole('radio', { name: stufe }).click();
  await host.getByRole('button', { name: 'Raum eröffnen' }).click();
  const code = (await host.getByLabel('Raumcode').textContent())!.trim();
  expect(code).toMatch(/^[A-Z0-9]{4}$/);
  return { host, code };
}

async function beitreten(context: BrowserContext, code: string, name: string, stufe?: Stufe) {
  const gast = await geraetOeffnen(context);
  await gast.getByLabel('Dein Name').fill(name);
  if (stufe) await gast.getByRole('radiogroup', { name: 'Schwierigkeit', exact: true }).getByRole('radio', { name: stufe }).click();
  await gast.getByLabel('Raumcode').fill(code.toLowerCase());
  await gast.getByRole('button', { name: 'Beitreten' }).click();
  return gast;
}

const spielerImRaum = (page: Page) => page.getByRole('list', { name: 'Spieler im Raum' });

test('zwei Geräte reihum: Lobby, Züge, Zuschauen, Neuladen, zurück zum Raum, verlassen', async ({ context }) => {
  await vorbereiten(context);
  const { host, code } = await raumEroeffnen(context, 'Anna');
  const gast = await beitreten(context, code, 'Ben');

  // Lobby
  await expect(gast.getByText('Warte, bis Anna das Spiel startet …')).toBeVisible();
  await expect(spielerImRaum(host)).toContainText('Ben');
  await expect(spielerImRaum(gast)).toContainText('Anna');
  await host.getByRole('radio', { name: /^(✓ )?Reihum/ }).click();
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

test('Mehrere Geräte: Einstieg sichtbar; bei 320 px kein horizontales Scrollen', async ({ context }) => {
  await vorbereiten(context);
  const normal = await context.newPage();
  await normal.goto('./');
  await expect(normal.getByRole('button', { name: 'Mit mehreren Geräten spielen' })).toBeVisible();

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

test('drei Geräte „Alle gleichzeitig“: gleiche Frage, Warten, Timeout, Ergebnisse, Kategorie reihum, Rangliste', async ({
  context,
}) => {
  await vorbereiten(context);
  const { host: anna, code } = await raumEroeffnen(context, 'Anna');
  const ben = await beitreten(context, code, 'Ben');
  const cleo = await beitreten(context, code, 'Cleo');
  const alle = [anna, ben, cleo];
  await expect(spielerImRaum(anna).getByRole('listitem')).toHaveCount(3);

  // Standard im Raum: „Alle gleichzeitig“; „Vorheriger Spieler wählt“ ist dann gesperrt
  await expect(anna.getByRole('radio', { name: /Alle gleichzeitig/ })).toHaveAttribute('aria-checked', 'true');
  await expect(anna.getByRole('radio', { name: /Vorheriger Spieler wählt/ })).toBeDisabled();
  await expect(anna.getByText('In jeder Runde beantworten alle dieselbe Frage.')).toBeVisible();
  await anna.getByRole('radio', { name: '5', exact: true }).click();
  await anna.getByRole('button', { name: 'Spiel starten' }).click();

  // Runde 1: Anna wählt für alle, keine Übergabe
  await expect(anna.getByRole('heading', { name: 'Wähle eine Kategorie für alle' })).toBeVisible();
  await expect(ben.getByRole('heading', { name: 'Anna wählt eine Kategorie für alle' })).toBeVisible();
  const frage = await frageOeffnen(anna, 'geografie');
  for (const p of [ben, cleo]) {
    await expect(p.getByRole('heading', { level: 1 })).toHaveText(frage);
    await expect(p.locator('.antwort').first()).toBeEnabled();
  }

  // Ben richtig nach 3 s, Anna falsch, Cleo antwortet nicht
  await anna.clock.runFor(3000);
  await ben.locator('.antwort', { hasText: /Richtig/ }).click();
  await expect(ben.getByText('Warte auf die anderen … (1/3)')).toBeVisible();
  await expect(ben.locator('.antwort').first()).toBeDisabled();
  await anna.locator('.antwort', { hasText: 'Falsch A' }).click();
  await expect(anna.getByText('Warte auf die anderen … (2/3)')).toBeVisible();
  await expect(cleo.locator('.antwort').first()).toBeEnabled();
  // Cleos Zeit läuft nach 15 s ab; der Host wartet noch die Netz-Toleranz ab (1.5 s), dann Feedback
  await anna.clock.runFor(12_100);
  await expect(anna.getByRole('heading', { name: 'Leider falsch' })).toHaveCount(0);
  await anna.clock.runFor(1_500);

  // Feedback: jeder sieht sein eigenes Ergebnis und alle Ergebnisse
  await expect(ben.getByRole('heading', { name: 'Richtig!' })).toBeVisible();
  await expect(ben.locator('.punkte')).toContainText('+82 Punkte');
  await expect(anna.getByRole('heading', { name: 'Leider falsch' })).toBeVisible();
  await expect(cleo.getByRole('heading', { name: 'Zeit abgelaufen' })).toBeVisible();
  for (const p of alle) {
    const ergebnisse = p.getByRole('list', { name: 'Ergebnisse' });
    await expect(ergebnisse.getByRole('listitem').filter({ hasText: 'Ben' })).toContainText('+82');
    await expect(ergebnisse.getByRole('listitem').filter({ hasText: 'Cleo' })).toContainText('keine Antwort');
    await expect(ergebnisse.getByRole('listitem').filter({ hasText: 'Anna' })).toContainText('Falsch A');
  }
  await expect(ben.getByText('Warte auf Anna …')).toBeVisible();
  await expect(ben.getByRole('button', { name: 'Weiter' })).toHaveCount(0);
  await weiter(anna);

  // Runde 2: Ben wählt für alle; jeder sieht oben seine eigenen Punkte
  await expect(ben.getByRole('heading', { name: 'Wähle eine Kategorie für alle' })).toBeVisible();
  await expect(anna.getByRole('heading', { name: 'Ben wählt eine Kategorie für alle' })).toBeVisible();
  await expect(ben.getByText('Runde 2/5 · 82 P.')).toBeVisible();
  await expect(cleo.getByText('Runde 2/5 · 0 P.')).toBeVisible();

  // Runden 2–5: alle sofort richtig → Feedback ohne Warten auf den Timer
  const waehlende = [ben, cleo, anna, ben];
  for (const [i, waehlt] of waehlende.entries()) {
    await waehlt.getByRole('button', { name: KAT_NAME[i % 2 ? 'sport' : 'geografie'] }).click();
    await warteAufFrage(waehlt);
    for (const p of alle) await p.locator('.antwort', { hasText: /Richtig/ }).click();
    for (const p of alle) await expect(p.getByRole('heading', { name: 'Richtig!' })).toBeVisible();
    await anna.getByRole('button', { name: i === 3 ? 'Zur Rangliste' : 'Weiter' }).click();
  }

  // Rangliste: Ben gewinnt (82 + 4 × 100), Gäste warten auf den Host
  for (const p of alle) await expect(p.getByRole('heading', { name: 'Ben gewinnt!' })).toBeVisible();
  await expect(cleo.getByText('Warte auf Anna …')).toBeVisible();
  await expect(cleo.getByRole('button', { name: 'Raum verlassen' })).toBeVisible();
  await anna.getByRole('button', { name: 'Nochmals spielen' }).click();
  await expect(anna.getByRole('heading', { name: 'Wähle eine Kategorie für alle' })).toBeVisible();
  await expect(cleo.getByText('Runde 1/5 · 0 P.')).toBeVisible();
});

test('Beitritt per Link (QR-Code): Code vorausgefüllt, Beitreten zuerst', async ({ context }) => {
  await vorbereiten(context);
  const { host, code } = await raumEroeffnen(context, 'Anna');
  await expect(host.getByRole('img', { name: 'QR-Code zum Beitreten' }).locator('svg')).toBeVisible();
  const link = (await host.getByLabel('Link zum Beitreten').textContent())!.trim();
  expect(link).toMatch(new RegExp(`\\?kanal=tabs&raum=${code}$`));

  const gast = await context.newPage();
  await gast.goto(link);
  await expect(gast.getByRole('heading', { name: 'Raum beitreten' })).toBeVisible();
  await expect(gast.getByLabel('Raumcode')).toHaveValue(code);
  // Der Raum-Parameter verschwindet aus der Adresse (Neuladen öffnet nicht erneut den Beitritt)
  expect(new URL(gast.url()).searchParams.has('raum')).toBe(false);
  // „Raum beitreten“ steht vor „Raum eröffnen“
  const titel = await gast.getByRole('heading', { level: 2 }).allTextContents();
  expect(titel.indexOf('Raum beitreten')).toBeLessThan(titel.indexOf('Raum eröffnen'));
  await gast.getByLabel('Dein Name').fill('Ben');
  await gast.getByRole('button', { name: 'Beitreten' }).click();
  await expect(gast.getByText('Warte, bis Anna das Spiel startet …')).toBeVisible();
  // Gäste sehen den Link auch und können ihn weitergeben
  await expect(gast.getByLabel('Link zum Beitreten')).toHaveText(link);
});

test('Beitritt abgelehnt, wenn das Gerät andere Fragen hat als der Host', async ({ context }) => {
  await vorbereiten(context);
  const { host, code } = await raumEroeffnen(context, 'Anna');
  const gast = await context.newPage();
  // Veralteter Fragenstand nur auf diesem Gerät
  await gast.route('**/questions.json', (route) => {
    const pool = fixturePool();
    pool.fragen.pop();
    return route.fulfill({ json: pool });
  });
  await gast.goto('./?kanal=tabs');
  await gast.getByRole('button', { name: 'Mit mehreren Geräten spielen' }).click();
  await gast.getByLabel('Dein Name').fill('Ben');
  await gast.getByLabel('Raumcode').fill(code);
  await gast.getByRole('button', { name: 'Beitreten' }).click();
  await expect(gast.getByRole('alert')).toHaveText(
    'Dieses Gerät und der Host haben nicht dieselben Fragen. Bitte auf beiden Geräten die App neu laden.',
  );
  await expect(spielerImRaum(host).getByRole('listitem')).toHaveCount(1);
});

/** Geografie 1–2 leicht, 3–6 schwer */
function stufenPool() {
  const pool = fixturePool();
  for (const f of pool.fragen) {
    if (f.kategorie === 'geografie') f.schwierigkeit = Number(f.id.split('-')[1]) <= 2 ? 1 : 3;
  }
  return pool;
}

test('Schwierigkeit reihum: jedes Gerät wählt seine Stufe beim Beitreten', async ({ context }) => {
  await vorbereiten(context, stufenPool());
  const { host: anna, code } = await raumEroeffnen(context, 'Anna', 'Leicht');
  const ben = await beitreten(context, code, 'Ben', 'Schwer');
  await expect(spielerImRaum(anna)).toContainText('Ben');

  await anna.getByRole('radio', { name: /^(✓ )?Reihum/ }).click();
  const liste = anna.getByRole('list', { name: 'Schwierigkeit pro Spieler' });
  await expect(liste).toContainText('Anna: Leicht');
  await expect(liste).toContainText('Ben: Schwer');
  await anna.getByRole('radio', { name: '5', exact: true }).click();
  await anna.getByRole('button', { name: 'Spiel starten' }).click();

  await anna.getByRole('button', { name: 'Bereit' }).click();
  expect(await frageOeffnen(anna, 'geografie')).toMatch(/Testfrage geografie [12]:/);
  await beantworten(anna, { typ: 'falsch' });
  await weiter(anna);

  await ben.getByRole('button', { name: 'Bereit' }).click();
  expect(await frageOeffnen(ben, 'geografie')).toMatch(/Testfrage geografie [3-6]:/);
});

test('Schwierigkeit „Alle gleichzeitig“: eine Stufe für alle, vom Host gewählt', async ({ context }) => {
  await vorbereiten(context, stufenPool());
  const { host: anna, code } = await raumEroeffnen(context, 'Anna', 'Leicht');
  const ben = await beitreten(context, code, 'Ben', 'Leicht');
  await expect(spielerImRaum(anna)).toContainText('Ben');

  await expect(anna.getByText('deshalb gilt eine Stufe für alle')).toBeVisible();
  await anna.getByRole('radiogroup', { name: 'Schwierigkeit', exact: true }).getByRole('radio', { name: 'Schwer' }).click();
  await anna.getByRole('radio', { name: '5', exact: true }).click();
  await anna.getByRole('button', { name: 'Spiel starten' }).click();

  // Trotz persönlicher Wahl „Leicht“ kommen schwere Fragen
  const frage = await frageOeffnen(anna, 'geografie');
  expect(frage).toMatch(/Testfrage geografie [3-6]:/);
  await expect(ben.getByRole('heading', { level: 1 })).toHaveText(frage);
});
