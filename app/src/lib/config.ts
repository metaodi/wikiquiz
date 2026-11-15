/** Zentrale, konfigurierbare Spielparameter. */

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

/** Dauer der Zufalls-Animation (ms) */
export const ZUFALL_ANIMATION_MS = 1600;
/** Einblende-Animation der Antworten (ms); erst danach startet der Timer */
export const EINBLENDEN_MS = 450;
