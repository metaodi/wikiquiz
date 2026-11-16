/** Fragenauswahl: nie doppelt im Spiel, zuletzt gestellte Fragen bevorzugt vermeiden. */
import { KATEGORIEN } from './categories';
import type { Frage, KategorieId } from './types';

export type Rng = () => number;

export function verfuegbar(pool: Frage[], kategorie: KategorieId, gestellt: string[]): Frage[] {
  const g = new Set(gestellt);
  return pool.filter((f) => f.kategorie === kategorie && !g.has(f.id));
}

export function verfuegbareKategorien(
  pool: Frage[],
  gestellt: string[],
  erlaubt: KategorieId[] = KATEGORIEN.map((k) => k.id),
): KategorieId[] {
  return erlaubt.filter((id) => verfuegbar(pool, id, gestellt).length > 0);
}

export function anzahlProKategorie(pool: Frage[], gestellt: string[]): Record<KategorieId, number> {
  const res = Object.fromEntries(KATEGORIEN.map((k) => [k.id, 0])) as Record<KategorieId, number>;
  const g = new Set(gestellt);
  for (const f of pool) if (!g.has(f.id) && f.kategorie in res) res[f.kategorie]++;
  return res;
}

/**
 * Fragen, deren Quelle (Wikipedia-Artikel) im laufenden Spiel noch nicht vorkam. Zwei Fragen zum selben
 * Artikel verraten sich oft gegenseitig („Wer komponierte «Ein deutsches Requiem»?“ und „Wo wurde
 * Johannes Brahms geboren?“). Gibt es keine solchen Fragen mehr, bleiben alle Kandidaten erlaubt.
 */
export function andereQuellen(kandidaten: Frage[], pool: Frage[], gestellt: string[]): Frage[] {
  const g = new Set(gestellt);
  const benutzt = new Set(pool.filter((f) => g.has(f.id)).map((f) => f.quelle_url));
  const neu = kandidaten.filter((f) => !benutzt.has(f.quelle_url));
  return neu.length > 0 ? neu : kandidaten;
}

/**
 * Wählt eine Frage der Kategorie, möglichst zu einem Artikel, der im Spiel noch nicht vorkam.
 * Fragen, die nicht in der History stehen, werden bevorzugt; sind alle schon einmal gestellt
 * worden, kommt die am längsten zurückliegende dran.
 */
export function waehleFrage(
  pool: Frage[],
  kategorie: KategorieId,
  gestellt: string[],
  history: string[],
  rng: Rng = Math.random,
): Frage | null {
  const offen = verfuegbar(pool, kategorie, gestellt);
  if (offen.length === 0) return null;
  const kandidaten = andereQuellen(offen, pool, gestellt);
  const pos = new Map(history.map((id, i) => [id, i]));
  const frisch = kandidaten.filter((f) => !pos.has(f.id));
  if (frisch.length > 0) return frisch[Math.floor(rng() * frisch.length)];
  return kandidaten.reduce((a, b) => (pos.get(a.id)! <= pos.get(b.id)! ? a : b));
}

export function mischen<T>(liste: T[], rng: Rng = Math.random): T[] {
  const a = [...liste];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
