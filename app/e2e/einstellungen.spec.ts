import { expect, test } from '@playwright/test';
import { beantworten, fixturePool, frageOeffnen, KAT_NAME, oeffnen, setup, uebergabe, warteAufFrage, weiter } from './helfer';

test('Kategorienauswahl und „Immer Zufall“: nur gewählte Kategorien, keine eigene Wahl', async ({ page }) => {
  await oeffnen(page);
  await setup(page, ['Solo'], 5, async () => {
    // Standard: alle Kategorien aktiv, „Selbst wählen“, „Vorheriger Spieler“ erst ab 2 Spielern
    await expect(page.getByRole('radio', { name: /Selbst wählen/ })).toBeChecked();
    await expect(page.getByRole('radio', { name: /Vorheriger Spieler wählt/ })).toBeDisabled();
    await expect(page.getByRole('button', { name: KAT_NAME.kunst })).toHaveAttribute('aria-pressed', 'true');

    // Keine Kategorie → Start gesperrt
    await page.getByRole('button', { name: 'Keine', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('mindestens eine Kategorie');
    await expect(page.getByRole('button', { name: 'Spiel starten' })).toBeDisabled();
    // Nur Kategorien ohne Fragen → weiterhin gesperrt
    await page.getByRole('button', { name: /Geschichte/ }).click();
    await expect(page.getByRole('alert')).toContainText('noch keine Fragen');
    await expect(page.getByRole('button', { name: 'Spiel starten' })).toBeDisabled();

    await page.getByRole('button', { name: /Geschichte/ }).click();
    await page.getByRole('button', { name: KAT_NAME.kunst }).click();
    await page.getByRole('button', { name: KAT_NAME.sport }).click();
    await page.getByRole('radio', { name: /Immer Zufall/ }).click();
  });

  // Kein Kategorie-Screen: es wird sofort gelost, nur Kunst und Sport
  for (let i = 0; i < 4; i++) {
    await expect(page.getByText('Zufall …')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Wähle eine Kategorie' })).toHaveCount(0);
    expect(await warteAufFrage(page)).toMatch(/Testfrage (kunst|sport)/);
    await beantworten(page, { typ: 'falsch' });
    await weiter(page);
  }
  // Alle Fragen der gewählten Kategorien gestellt (Geografie bleibt aussen vor)
  await expect(page.getByText('Es sind keine Fragen mehr übrig.')).toBeVisible();

  // Einstellungen werden für das nächste Spiel gemerkt
  await page.getByRole('button', { name: 'Zur Rangliste' }).click();
  await page.getByRole('button', { name: 'Neues Spiel' }).click();
  await expect(page.getByRole('radio', { name: /Immer Zufall/ })).toBeChecked();
  await expect(page.getByRole('button', { name: KAT_NAME.geografie })).toHaveAttribute('aria-pressed', 'false');
  await expect(page.getByRole('button', { name: KAT_NAME.sport })).toHaveAttribute('aria-pressed', 'true');
});

test('„Vorheriger Spieler wählt“: Wahl vor der Übergabe, auch per Zufall', async ({ page }) => {
  await oeffnen(page);
  await setup(page, ['Anna', 'Ben'], 5, async () => {
    await page.getByRole('radio', { name: /Vorheriger Spieler wählt/ }).click();
  });

  // Erste Frage: Ben (der Letzte) wählt für Anna – noch vor der Übergabe
  await expect(page.getByRole('heading', { name: 'Kategorie für Anna' })).toBeVisible();
  await expect(page.getByText(/Ben wählt/)).toBeVisible();
  await page.getByRole('button', { name: KAT_NAME.sport }).click();
  await uebergabe(page, 'Anna');
  expect(await warteAufFrage(page)).toMatch(/Testfrage sport/);
  expect(await beantworten(page, { typ: 'richtig' })).toBe(100);
  await weiter(page);

  // Anna wählt für Ben: Zufall – die Animation sieht erst Ben nach der Übergabe
  await expect(page.getByRole('heading', { name: 'Kategorie für Ben' })).toBeVisible();
  await expect(page.getByText(/Anna wählt/)).toBeVisible();
  await page.getByRole('button', { name: /Zufall/ }).click();
  await expect(page.getByText('Zufall …')).toHaveCount(0);
  await uebergabe(page, 'Ben');
  await expect(page.getByText('Zufall …')).toBeVisible();
  await warteAufFrage(page);
  await beantworten(page, { typ: 'falsch' });
  await weiter(page);

  // Nach dem Zwischenstand wählt wieder Ben für Anna; nach Neuladen bleibt die Wahl erhalten
  await page.getByRole('button', { name: 'Runde 2 starten' }).click();
  await expect(page.getByRole('heading', { name: 'Kategorie für Anna' })).toBeVisible();
  await page.getByRole('button', { name: KAT_NAME.kunst }).click();
  await page.reload();
  await uebergabe(page, 'Anna');
  expect(await warteAufFrage(page)).toMatch(/Testfrage kunst/);
});

test('Neue Kategorien: bei früher „alle“ automatisch gewählt, Allgemeinwissen entfällt', async ({ page }) => {
  const alteSechs = ['naturwissenschaften', 'kunst', 'geschichte', 'sport', 'geografie', 'allgemeinwissen'];
  const gespeichert = (kategorien: string[]) =>
    JSON.stringify({ namen: ['Anna'], farben: ['#e53935'], runden: 5, modus: 'selbst', kategorien });

  // Älterer Speicherstand (vor Schweiz/Star Wars) mit allen sechs Kategorien
  await page.addInitScript((wert) => {
    if (!sessionStorage.getItem('init')) localStorage.setItem('wikiquiz:players:v1', wert);
    sessionStorage.setItem('init', '1');
  }, gespeichert(alteSechs));
  await oeffnen(page);
  for (const name of [/Schweiz/, /Star Wars/, /Harry Potter/, /Essen & Genuss/, /Tiere & Natur/, KAT_NAME.kunst]) {
    await expect(page.getByRole('button', { name })).toHaveAttribute('aria-pressed', 'true');
  }
  await expect(page.getByRole('button', { name: /Allgemeinwissen/ })).toHaveCount(0);

  // Bewusste Auswahl (nur Kunst) bleibt erhalten
  await page.evaluate((wert) => localStorage.setItem('wikiquiz:players:v1', wert), gespeichert(['kunst']));
  await page.reload();
  await expect(page.getByRole('button', { name: KAT_NAME.kunst })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', { name: /Schweiz/ })).toHaveAttribute('aria-pressed', 'false');
  await expect(page.getByRole('button', { name: /Star Wars/ })).toHaveAttribute('aria-pressed', 'false');
});

test('Schwierigkeit pro Spieler: Fragen der gewählten Stufe, Ausweichen, gemerkt', async ({ page }) => {
  // Geografie 1–2 leicht, 3–6 schwer
  const pool = fixturePool();
  for (const f of pool.fragen) {
    if (f.kategorie === 'geografie') f.schwierigkeit = Number(f.id.split('-')[1]) <= 2 ? 1 : 3;
  }
  await oeffnen(page, pool);
  await setup(page, ['Anna', 'Ben'], 5, async () => {
    // Standard „Mittel“
    await expect(page.getByRole('radiogroup', { name: 'Schwierigkeit Spieler 1' }).getByRole('radio', { name: 'Mittel' })).toBeChecked();
    await page.getByRole('radiogroup', { name: 'Schwierigkeit Spieler 1' }).getByRole('radio', { name: 'Leicht' }).click();
    await page.getByRole('radiogroup', { name: 'Schwierigkeit Spieler 2' }).getByRole('radio', { name: 'Schwer' }).click();
  });

  // Anna bekommt nur leichte, Ben nur schwere Fragen
  for (let runde = 1; runde <= 2; runde++) {
    await uebergabe(page, 'Anna');
    expect(await frageOeffnen(page, 'geografie')).toMatch(/Testfrage geografie [12]:/);
    await beantworten(page, { typ: 'falsch' });
    await weiter(page);
    await uebergabe(page, 'Ben');
    expect(await frageOeffnen(page, 'geografie')).toMatch(/Testfrage geografie [3-6]:/);
    await beantworten(page, { typ: 'falsch' });
    await weiter(page);
    await page.getByRole('button', { name: `Runde ${runde + 1} starten` }).click();
  }

  // Leichte Geografie-Fragen aufgebraucht → Anna bekommt die nächstliegende Stufe
  await uebergabe(page, 'Anna');
  expect(await frageOeffnen(page, 'geografie')).toMatch(/Testfrage geografie [3-6]:/);
  await beantworten(page, { typ: 'falsch' });

  // Die Wahl wird für das nächste Spiel gemerkt
  page.once('dialog', (d) => d.accept());
  await page.getByRole('button', { name: 'Spiel beenden' }).click();
  await expect(page.getByRole('radiogroup', { name: 'Schwierigkeit Spieler 1' }).getByRole('radio', { name: 'Leicht' })).toBeChecked();
  await expect(page.getByRole('radiogroup', { name: 'Schwierigkeit Spieler 2' }).getByRole('radio', { name: 'Schwer' })).toBeChecked();
});
