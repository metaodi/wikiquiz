import { expect, test } from '@playwright/test';
import { beantworten, frageOeffnen, setup, weiter } from './helfer';

/** Drei Geografie-Fragen, zwei davon zum selben Artikel */
function pool() {
  const frage = (id: string, artikel: string) => ({
    id,
    kategorie: 'geografie',
    frage: `Testfrage ${id}: Welche Antwort ist richtig?`,
    antworten: ['Richtig', 'Falsch A', 'Falsch B', 'Falsch C'],
    korrekt_index: 0,
    schwierigkeit: 1,
    quelle_typ: 'wikipedia',
    quelle_url: `https://de.wikipedia.org/wiki/${artikel}`,
    lizenz: 'CC BY-SA 4.0',
  });
  return {
    version: 1,
    generiert_am: '2026-11-15T12:00:00Z',
    fragen: [frage('brahms-1', 'Johannes_Brahms'), frage('brahms-2', 'Johannes_Brahms'), frage('bach-1', 'Bach')],
  };
}

test('zwei Fragen zum selben Artikel kommen nicht nacheinander, solange es andere gibt', async ({ page }) => {
  // Zufall fest auf 0: Ohne die Regel käme nach brahms-1 als Nächstes brahms-2
  await page.addInitScript(() => {
    Math.random = () => 0;
  });
  await page.clock.install({ time: new Date('2026-11-15T10:00:00Z') });
  await page.clock.pauseAt(new Date('2026-11-15T10:00:01Z'));
  await page.route('**/questions.json', (route) => route.fulfill({ json: pool() }));
  await page.goto('./');
  await setup(page, ['Solo'], 5);

  const gesehen: string[] = [];
  for (let i = 0; i < 3; i++) {
    gesehen.push(/Testfrage (\S+):/.exec(await frageOeffnen(page, 'geografie'))![1]);
    await beantworten(page, { typ: 'richtig' });
    await weiter(page);
  }
  expect(gesehen).toHaveLength(3);
  // Die zweite Frage stammt aus einem anderen Artikel als die erste
  expect(gesehen[1].split('-')[0]).not.toBe(gesehen[0].split('-')[0]);
  expect(new Set(gesehen).size).toBe(3);
});
