import type { Pool } from './types';

/** Lädt den Fragenpool (vom Service Worker vorab gecacht). */
export async function ladePool(): Promise<Pool> {
  const res = await fetch(`${import.meta.env.BASE_URL}questions.json`);
  if (!res.ok) throw new Error(`Fragen konnten nicht geladen werden (HTTP ${res.status})`);
  const pool = (await res.json()) as Pool;
  // Defensive Prüfung, damit eine fehlerhafte Frage das Spiel nicht blockiert
  pool.fragen = pool.fragen.filter(
    (f) =>
      Array.isArray(f.antworten) &&
      f.antworten.length === 4 &&
      f.korrekt_index >= 0 &&
      f.korrekt_index < 4 &&
      typeof f.frage === 'string',
  );
  return pool;
}
