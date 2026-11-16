import type { Pool } from './types';

/**
 * Kurze Kennung des Fragenstands (FNV-1a über alle Frage-IDs). Mehrere Geräte vergleichen sie beim Beitritt,
 * denn übertragen werden nur Frage-IDs – ein Gerät mit veraltetem Cache fände Fragen nicht.
 */
export function poolKennung(pool: Pick<Pool, 'fragen'>): string {
  let h = 0x811c9dc5;
  for (const f of pool.fragen) {
    for (let i = 0; i < f.id.length; i++) {
      h ^= f.id.charCodeAt(i);
      h = Math.imul(h, 0x01000193);
    }
    h ^= 0x2c; // Trennzeichen zwischen IDs
    h = Math.imul(h, 0x01000193);
  }
  return `${pool.fragen.length}-${(h >>> 0).toString(16)}`;
}

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
