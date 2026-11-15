import { expect, test } from '@playwright/test';
import { beantworten, EINBLENDEN, frageOeffnen, oeffnen, setup, uebergabe, weiter } from './helfer';

test.describe('1 Spieler', () => {
  test('Punkte, falsche Antwort, Timeout, erschöpfte Kategorie, Spielende', async ({ page }) => {
    await oeffnen(page);
    await setup(page, ['Solo'], 15);

    // Kein Übergabe-Screen bei einem Spieler
    await expect(page.getByRole('heading', { name: 'Wähle eine Kategorie' })).toBeVisible();

    // 1) Sofort richtig → 100 Punkte
    await frageOeffnen(page, 'geografie');
    expect(await beantworten(page, { typ: 'richtig' })).toBe(100);
    await expect(page.getByRole('link', { name: /Mehr auf Wikipedia/ })).toHaveAttribute(
      'href',
      /^https:\/\/de\.wikipedia\.org\/wiki\/Test_geografie_/,
    );
    await weiter(page);

    // 2) Richtig nach 7.5 s → round(100 − 90 × 0.5) = 55
    await frageOeffnen(page, 'geografie');
    expect(await beantworten(page, { typ: 'richtig', nachMs: 7500 })).toBe(55);
    await weiter(page);

    // 3) Falsche Antwort → 0
    await frageOeffnen(page, 'geografie');
    await beantworten(page, { typ: 'falsch' });
    await weiter(page);

    // 4) Timeout → 0
    await frageOeffnen(page, 'geografie');
    await beantworten(page, { typ: 'timeout' });
    await expect(page.getByText('Total 155')).toBeVisible();
    await weiter(page);

    // Restliche Geografie-Fragen aufbrauchen, jede Frage nur einmal
    const gesehen = new Set<string>();
    for (let i = 0; i < 2; i++) {
      gesehen.add(await frageOeffnen(page, 'geografie'));
      await beantworten(page, { typ: 'falsch' });
      await weiter(page);
    }
    expect(gesehen.size).toBe(2);

    // Erschöpfte Kategorie: ausgegraut, Hinweis beim Antippen, andere Kategorie wählbar
    const geo = page.getByRole('button', { name: /Geografie/ });
    await expect(geo).toContainText('keine Fragen mehr');
    await geo.click({ force: true });
    await expect(page.getByRole('alert')).toContainText('Alle Fragen aus „Geografie“ wurden in diesem Spiel schon gestellt');
    await expect(page.getByRole('button', { name: /Naturwissenschaften/ })).toContainText('bald verfügbar');

    // Restliche 4 Fragen über Zufall: nur noch Kunst/Sport
    for (let i = 0; i < 4; i++) {
      const text = await frageOeffnen(page, 'zufall');
      expect(text).toMatch(/Testfrage (kunst|sport)/);
      await beantworten(page, { typ: 'falsch' });
      await weiter(page);
    }

    // Alle 10 Fragen gestellt, aber 15 Runden gewählt → Spiel endet vorzeitig
    await expect(page.getByText('Es sind keine Fragen mehr übrig.')).toBeVisible();
    await page.getByRole('button', { name: 'Zur Rangliste' }).click();
    await expect(page.getByRole('heading', { name: 'Geschafft!' })).toBeVisible();
    await expect(page.getByText('155 Punkte')).toBeVisible();

    // Nochmals spielen: gleicher Spieler, Punkte zurückgesetzt, alle Kategorien wieder offen
    await page.getByRole('button', { name: 'Nochmals spielen' }).click();
    await expect(page.getByText('Runde 1/15 · 0 P.')).toBeVisible();
    await expect(page.getByRole('button', { name: /Geografie/ })).not.toContainText('keine Fragen mehr');
  });
});

test.describe('4 Spieler', () => {
  test('Übergabe, Zwischenstand, Rangliste mit geteilten Rängen, neues Spiel', async ({ page }) => {
    await oeffnen(page);
    await setup(page, ['Anna', 'Ben', 'Cleo', 'Dario'], 5);

    const runde = async (nr: number) => {
      await uebergabe(page, 'Anna');
      await expect(page.getByText(`Runde ${nr}/5`)).toBeVisible();
      await frageOeffnen(page, nr % 2 ? 'geografie' : 'zufall');
      expect(await beantworten(page, { typ: 'richtig' })).toBe(100);
      await weiter(page);

      await uebergabe(page, 'Ben');
      await frageOeffnen(page, 'geografie');
      expect(await beantworten(page, { typ: 'richtig' })).toBe(100);
      await weiter(page);

      await uebergabe(page, 'Cleo');
      await frageOeffnen(page, 'zufall');
      await beantworten(page, { typ: 'falsch' });
      await weiter(page);

      await uebergabe(page, 'Dario');
      await frageOeffnen(page, 'zufall');
      await beantworten(page, { typ: 'timeout' });
      await weiter(page);
    };

    await runde(1);
    // Zwischenstand nach Runde 1
    await expect(page.getByRole('heading', { name: 'Zwischenstand' })).toBeVisible();
    await expect(page.getByText('Runde 1 von 5 beendet')).toBeVisible();
    const zeilen = page.locator('.tabelle li');
    await expect(zeilen).toHaveCount(4);
    await expect(zeilen.nth(0)).toContainText('1.');
    await expect(zeilen.nth(1)).toContainText('1.');
    await expect(zeilen.nth(2)).toContainText('3.');
    await expect(zeilen.nth(3)).toContainText('3.');
    await page.getByRole('button', { name: 'Runde 2 starten' }).click();

    await runde(2);
    await page.getByRole('button', { name: 'Runde 3 starten' }).click();

    // Pool hat nur 10 Fragen → nach 2 Runden (8 Fragen) bleiben 2. Anna und Ben spielen sie.
    await uebergabe(page, 'Anna');
    await frageOeffnen(page, 'zufall');
    await beantworten(page, { typ: 'richtig' });
    await weiter(page);
    await uebergabe(page, 'Ben');
    await frageOeffnen(page, 'zufall');
    await beantworten(page, { typ: 'richtig' });
    await weiter(page);

    // Cleo: keine Fragen mehr → Spiel endet
    await uebergabe(page, 'Cleo');
    await expect(page.getByText('Es sind keine Fragen mehr übrig.')).toBeVisible();
    await page.getByRole('button', { name: 'Zur Rangliste' }).click();

    await expect(page.getByRole('heading', { name: 'Gleichstand!' })).toBeVisible();
    await expect(page.getByText('Anna & Ben')).toBeVisible();
    await expect(page.getByText('teilen sich den Sieg mit 300 Punkten')).toBeVisible();

    // Neues Spiel → Setup mit vorbelegten Namen
    await page.getByRole('button', { name: 'Neues Spiel' }).click();
    await expect(page.getByLabel('Name Spieler 4')).toHaveValue('Dario');
  });
});

test.describe('Neuladen', () => {
  test('mitten in der Frage: gleiche Frage, Timer läuft gemäss timerStart weiter', async ({ page }) => {
    await oeffnen(page);
    await setup(page, ['Anna', 'Ben'], 5);
    await uebergabe(page, 'Anna');
    const frage = await frageOeffnen(page, 'geografie');
    const reihenfolge = await page.locator('.antwort .text').allTextContents();
    await page.clock.runFor(5000);

    await page.reload();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(frage);
    expect(await page.locator('.antwort .text').allTextContents()).toEqual(reihenfolge);
    // Timer wurde nicht neu gestartet: ca. 10 s übrig
    await expect(page.locator('.zahl')).toHaveText('10');
    await expect(page.locator('.antwort').first()).toBeEnabled();

    // Antwort nach insgesamt 6 s → round(100 − 90 × 6/15) = 64
    await page.clock.runFor(1000);
    await page.locator('.antwort', { hasText: /Richtig/ }).click();
    await expect(page.getByText('+64 Punkte')).toBeVisible();
  });

  test('nach Ablauf der Zeit: Frage zählt als Timeout', async ({ page }) => {
    await oeffnen(page);
    await setup(page, ['Solo'], 5);
    await frageOeffnen(page, 'geografie');
    await page.clock.runFor(2000);
    // App ist z. B. 20 s im Hintergrund, dann wird neu geladen
    await page.clock.fastForward(20_000);
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Zeit abgelaufen' })).toBeVisible();
    await expect(page.getByText('0 Punkte · Total 0')).toBeVisible();
  });

  test('auf Übergabe- und Feedback-Screen bleibt der Spielstand erhalten', async ({ page }) => {
    await oeffnen(page);
    await setup(page, ['Anna', 'Ben'], 5);
    await uebergabe(page, 'Anna');
    await frageOeffnen(page, 'geografie');
    await page.locator('.antwort', { hasText: /Richtig/ }).click();
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Richtig!' })).toBeVisible();
    await expect(page.getByText('+100 Punkte')).toBeVisible();
    await weiter(page);
    await page.reload();
    await expect(page.getByRole('heading', { name: /Gib das Gerät an\s*Ben/ })).toBeVisible();
  });
});

test.describe('Timer', () => {
  test('startet erst nach dem Einblenden; Warnfarbe in den letzten 5 Sekunden', async ({ page }) => {
    await oeffnen(page);
    await setup(page, ['Solo'], 5);
    await page.getByRole('button', { name: /Geografie/ }).click();
    // Vor dem Einblenden: Antworten gesperrt, volle Zeit
    await expect(page.locator('.antwort').first()).toBeDisabled();
    await expect(page.locator('.zahl')).toHaveText('15');
    await page.clock.runFor(EINBLENDEN - 50);
    await expect(page.locator('.antwort').first()).toBeDisabled();
    await page.clock.runFor(50);
    await expect(page.locator('.antwort').first()).toBeEnabled();
    // Timer startet erst jetzt: nach dem Einblenden sind noch volle 15 s übrig
    await expect(page.locator('.zahl')).toHaveText('15');
    await expect(page.locator('.timer')).not.toHaveClass(/warnung/);
    await page.clock.runFor(9_900);
    await expect(page.locator('.timer')).not.toHaveClass(/warnung/);
    await page.clock.runFor(200);
    await expect(page.locator('.timer')).toHaveClass(/warnung/);
  });
});
