import { expect, test } from '@playwright/test';
import { oeffnen, setup } from './helfer';

test('kein horizontales Scrollen und Touch-Targets ≥ 48 px', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 });
  await oeffnen(page);
  const pruefen = async () => {
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
    const zuKlein = await page.evaluate(() =>
      [...document.querySelectorAll('button, a, input')]
        .map((el) => el.getBoundingClientRect())
        .filter((r) => r.width > 0 && (r.height < 47.5 || r.width < 47.5)).length,
    );
    expect(zuKlein).toBe(0);
  };
  await pruefen();
  await setup(page, ['Ein ziemlich langer Name'], 5);
  await pruefen();
});

test('Info-Seite mit Lizenzhinweisen', async ({ page }) => {
  await oeffnen(page);
  await page.getByRole('button', { name: 'Info, Quellen & Lizenzen' }).click();
  await expect(page.getByRole('link', { name: 'CC BY-SA 4.0' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'CC0 1.0' })).toBeVisible();
  await expect(page.getByText('Geografie: 6 Fragen')).toBeVisible();
});

test('UI-Texte ohne „ß“', async ({ page }) => {
  await oeffnen(page);
  expect(await page.locator('body').innerText()).not.toContain('ß');
});
