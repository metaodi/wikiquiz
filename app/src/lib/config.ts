/** Zentrale, konfigurierbare Spielparameter. */
import type { Schwierigkeit } from './types';

/** Zeitlimit pro Frage in Sekunden */
export const ZEITLIMIT_S = 15;
/** Ab dieser Restzeit wird der Timer hervorgehoben */
export const WARNUNG_AB_S = 5;

export const PUNKTE_MAX = 100;
export const PUNKTE_MIN = 10;

/**
 * Punkte für eine richtige Antwort nach `t` Sekunden (ab Timer-Start).
 * punkte = round(MAX − (MAX − MIN) × t / LIMIT) → 100 sofort, 10 kurz vor Ablauf, 0 nach Ablauf.
 */
export function punkteFuerZeit(t: number, limit = ZEITLIMIT_S): number {
  if (t > limit) return 0;
  const tt = Math.max(0, t);
  return Math.round(PUNKTE_MAX - (PUNKTE_MAX - PUNKTE_MIN) * (tt / limit));
}

export const RUNDEN_OPTIONEN = [5, 10, 15] as const;
export const RUNDEN_STANDARD = 10;
export const MAX_SPIELER = 4;

/** Schwierigkeitsstufen, wählbar pro Spieler im Setup */
export const SCHWIERIGKEITEN: { wert: Schwierigkeit; name: string }[] = [
  { wert: 1, name: 'Leicht' },
  { wert: 2, name: 'Mittel' },
  { wert: 3, name: 'Schwer' },
];
export const SCHWIERIGKEIT_STANDARD: Schwierigkeit = 2;
/**
 * Reihenfolge, in der Stufen gezogen werden: zuerst die gewählte, sind dort in der Kategorie keine Fragen
 * mehr offen, die nächstliegende. So bleibt jede Kategorie spielbar, solange sie überhaupt Fragen hat.
 */
export const SCHWIERIGKEIT_REIHENFOLGE: Record<Schwierigkeit, Schwierigkeit[]> = {
  1: [1, 2, 3],
  2: [2, 1, 3],
  3: [3, 2, 1],
};

export const SPIELER_FARBEN = ['#e53935', '#1e88e5', '#43a047', '#fb8c00', '#8e24aa', '#00897b'];
export const FARB_NAMEN: Record<string, string> = {
  '#e53935': 'Rot',
  '#1e88e5': 'Blau',
  '#43a047': 'Grün',
  '#fb8c00': 'Orange',
  '#8e24aa': 'Violett',
  '#00897b': 'Petrol',
};

/** Anzahl Frage-IDs, die über Spiele hinweg gemerkt und bevorzugt vermieden werden */
export const HISTORY_MAX = 300;

/**
 * Mehrere Geräte: Spielraum für Übertragungszeit. Eine Antwort zählt, wenn sie beim Host höchstens so viel später als
 * nach Ablauf der Zeit eintrifft; die Antwortzeit, die das Gerät meldet, darf höchstens so viel kürzer sein, als der Host
 * misst. Erst danach schliesst der Host eine Frage als Timeout ab.
 */
export const NETZ_TOLERANZ_S = 1.5;

/** Dauer der Zufalls-Animation (ms) */
export const ZUFALL_ANIMATION_MS = 1600;
/** Einblende-Animation der Antworten (ms); erst danach startet der Timer */
export const EINBLENDEN_MS = 450;
