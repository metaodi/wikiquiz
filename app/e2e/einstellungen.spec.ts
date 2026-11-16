import { expect, test } from '@playwright/test';
import { beantworten, KAT_NAME, oeffnen, setup, uebergabe, warteAufFrage, weiter } from './helfer';

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
  for (const name of [/Schweiz/, /Star Wars/, /Essen & Genuss/, /Tiere & Natur/, KAT_NAME.kunst]) {
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
