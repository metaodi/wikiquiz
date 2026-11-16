import { expect, type Page } from '@playwright/test';

/** Zeit bis die Antworten eingeblendet sind und der Timer läuft (EINBLENDEN_MS + Puffer) */
export const EINBLENDEN = 450;

type Kat = 'geografie' | 'kunst' | 'sport';

/**
 * Kleiner, deterministischer Fragenpool: 6× Geografie, 2× Kunst, 2× Sport.
 * Die richtige Antwort beginnt immer mit „Richtig“ – so können die Tests sie unabhängig
 * von der gemischten Reihenfolge finden.
 */
export function fixturePool() {
  const fragen = [];
  const anzahl: Record<Kat, number> = { geografie: 6, kunst: 2, sport: 2 };
  for (const [kat, n] of Object.entries(anzahl) as [Kat, number][]) {
    for (let i = 1; i <= n; i++) {
      const korrekt = i % 4;
      const antworten = ['Falsch A', 'Falsch B', 'Falsch C'];
      antworten.splice(korrekt, 0, `Richtig ${kat} ${i}`);
      fragen.push({
        id: `${kat}-${i}`,
        kategorie: kat,
        frage: `Testfrage ${kat} ${i}: Welche Antwort ist richtig?`,
        antworten,
        korrekt_index: korrekt,
        schwierigkeit: 1,
        quelle_typ: 'wikidata',
        quelle_url: `https://de.wikipedia.org/wiki/Test_${kat}_${i}`,
        lizenz: 'CC0',
        quelle_titel: `Test ${kat} ${i}`,
        quelle_id: `Q${i}`,
      });
    }
  }
  return { version: 1, generiert_am: '2026-11-15T12:00:00Z', fragen };
}

/** Uhr installieren, Fixture-Pool ausliefern, App öffnen. */
export async function oeffnen(page: Page, pool = fixturePool()) {
  // Uhr anhalten: Zeit vergeht nur über runFor/fastForward → exakte Punkte und Timeouts
  await page.clock.install({ time: new Date('2026-11-15T10:00:00Z') });
  await page.clock.pauseAt(new Date('2026-11-15T10:00:01Z'));
  await page.route('**/questions.json', (route) => route.fulfill({ json: pool }));
  await page.goto('./');
  await expect(page.getByRole('button', { name: 'Spiel starten' })).toBeVisible();
}

export async function setup(page: Page, namen: string[], runden: 5 | 10 | 15, vorStart?: () => Promise<void>) {
  for (let i = 0; i < namen.length; i++) {
    if (i > 0) await page.getByRole('button', { name: '+ Spieler hinzufügen' }).click();
    await page.getByLabel(`Name Spieler ${i + 1}`).fill(namen[i]);
  }
  await page.getByRole('radio', { name: String(runden), exact: true }).click();
  if (vorStart) await vorStart();
  await page.getByRole('button', { name: 'Spiel starten' }).click();
}

export async function uebergabe(page: Page, name: string) {
  await expect(page.getByRole('heading', { name: new RegExp(`Gib das Gerät an\\s*${name}`) })).toBeVisible();
  await page.getByRole('button', { name: 'Bereit' }).click();
}

export const KAT_NAME: Record<Kat, RegExp> = {
  geografie: /Geografie/,
  kunst: /Kunst, Musik/,
  sport: /Sport &/,
};

/** Kategorie wählen und warten, bis der Timer läuft. Gibt den Fragetext zurück. */
export async function frageOeffnen(page: Page, kat: Kat | 'zufall') {
  if (kat === 'zufall') {
    await page.getByRole('button', { name: /Zufall/ }).click();
    await expect(page.getByText('Zufall …')).toBeVisible();
    await page.clock.runFor(1000);
  } else {
    await page.getByRole('button', { name: KAT_NAME[kat] }).click();
  }
  return warteAufFrage(page);
}

/** Warten, bis die Frage sichtbar ist und der Timer läuft (ggf. nach der Zufalls-Animation). */
export async function warteAufFrage(page: Page) {
  const frage = page.getByRole('heading', { level: 1 });
  const sichtbar = page.locator('h1', { hasText: 'Testfrage' });
  for (let ms = 0; ms <= 3000 && (await sichtbar.count()) === 0; ms += 50) {
    await page.clock.runFor(50);
  }
  await expect(frage).toContainText('Testfrage');
  // In kleinen Schritten vorrücken, bis der Timer läuft (Antwortzeit danach ≈ 0)
  const antwort = page.locator('.antwort').first();
  for (let ms = 0; ms <= 3000 && (await antwort.isDisabled()); ms += 50) await page.clock.runFor(50);
  await expect(antwort).toBeEnabled();
  return (await frage.textContent())!;
}

export type Aktion = { typ: 'richtig' | 'falsch'; nachMs?: number } | { typ: 'timeout' };

/** Frage beantworten (oder ablaufen lassen) und das Feedback prüfen. Gibt die Punkte zurück. */
export async function beantworten(page: Page, aktion: Aktion): Promise<number> {
  if (aktion.typ === 'timeout') {
    await page.clock.runFor(15_500);
    await expect(page.getByRole('heading', { name: 'Zeit abgelaufen' })).toBeVisible();
    await expect(page.getByText('0 Punkte')).toBeVisible();
    return 0;
  }
  if (aktion.nachMs) await page.clock.runFor(aktion.nachMs);
  const ziel = aktion.typ === 'richtig' ? /Richtig/ : /Falsch A/;
  await page.locator('.antwort', { hasText: ziel }).click();
  if (aktion.typ === 'falsch') {
    await expect(page.getByRole('heading', { name: 'Leider falsch' })).toBeVisible();
    await expect(page.locator('li.falsch')).toContainText('Falsch A');
    await expect(page.locator('li.korrekt')).toContainText('Richtig');
    return 0;
  }
  await expect(page.getByRole('heading', { name: 'Richtig!' })).toBeVisible();
  const text = await page.locator('.punkte').textContent();
  return Number(/\+(\d+) Punkte/.exec(text!)![1]);
}

export async function weiter(page: Page) {
  await page.getByRole('button', { name: /^(Weiter|Zur Rangliste)$/ }).click();
}
