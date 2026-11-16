/**
 * Spielzüge als serialisierbare Nachrichten. Die Bildschirme lösen nur noch Aktionen aus;
 * `aktionAnwenden` wendet sie über die reinen Funktionen aus `game.ts` auf den Spielstand an.
 * Damit kann später ein Host-Gerät die Aktionen anderer Geräte ausführen (siehe docs/ARCHITEKTUR.md).
 */
import * as game from './game';
import type { Rng } from './picker';
import type { Frage, Spielstand } from './types';

export type Aktion =
  | { typ: 'bereit' }
  | { typ: 'kategorie'; wahl: game.Wahl }
  | { typ: 'zufallFertig' }
  | { typ: 'timerStarten' }
  /** `zeit`: Antwortzeit in Sekunden, wie sie das antwortende Gerät gemessen hat (nur mit mehreren Geräten) */
  | { typ: 'antworten'; index: number; zeit?: number }
  | { typ: 'zeitPruefen' }
  | { typ: 'weiter' }
  | { typ: 'zwischenstandWeiter' }
  | { typ: 'nochmals' }
  | { typ: 'beenden' };

/** Was das ausführende Gerät beisteuert: Fragen, eigene History, Uhrzeit und Zufall */
export interface Kontext {
  pool: Frage[];
  history: string[];
  jetzt: number;
  rng?: Rng;
  /** Spieler, der die Aktion auslöst (bestimmt der Host aus dem Gerät); nötig für „Alle gleichzeitig“ */
  spieler?: number;
  /** Mehrere Geräte: Spielraum für die Übertragung (`NETZ_TOLERANZ_S`), sonst 0 */
  toleranzMs?: number;
}

export interface Ergebnis {
  stand: Spielstand;
  /** Neu gezogene Frage (nur bei `kategorie`), damit das Gerät sie in seiner History vermerken kann */
  neueFrage?: Frage;
  /** Kategoriewahl gescheitert, Spielstand unverändert */
  fehler?: 'erschoepft' | 'alle_erschoepft';
}

/**
 * Zeitpunkt (Host-Uhr), zu dem die Antwort zählt. Ohne gemeldete Zeit: Eingang beim Host.
 * Mit gemeldeter Zeit (das Gerät misst ohne Übertragungsverzögerung): `timerStart + zeit`, aber nicht später als der
 * Eingang und höchstens `toleranzMs` früher – so lässt sich keine schnellere Antwort vortäuschen.
 */
export function antwortZeitpunkt(s: Spielstand, zeit: number | undefined, jetzt: number, toleranzMs: number): number {
  const start = s.zug?.timerStart;
  if (zeit === undefined || !Number.isFinite(zeit) || start === null || start === undefined) return jetzt;
  const gemeldet = start + Math.max(0, zeit) * 1000;
  return Math.min(jetzt, Math.max(gemeldet, jetzt - toleranzMs));
}

function aktuelleFrage(s: Spielstand, pool: Frage[]): Frage | undefined {
  return s.zug ? pool.find((f) => f.id === s.zug!.frageId) : undefined;
}

export function aktionAnwenden(s: Spielstand, aktion: Aktion, k: Kontext): Ergebnis {
  switch (aktion.typ) {
    case 'bereit':
      return { stand: game.bereit(s) };
    case 'kategorie': {
      // Verspätete oder doppelte Wahl (Doppeltipp, zweites Gerät) ist kein Fehler, sondern wirkungslos
      if (s.phase !== 'kategorie') return { stand: s };
      const r = game.kategorieWaehlen(s, k.pool, aktion.wahl, k.history, k.rng);
      return r.ok ? { stand: r.stand, neueFrage: r.frage } : { stand: s, fehler: r.grund };
    }
    case 'zufallFertig':
      return { stand: game.zufallFertig(s) };
    case 'timerStarten':
      return { stand: game.timerStarten(s, k.jetzt) };
    case 'antworten': {
      const frage = aktuelleFrage(s, k.pool);
      if (!frage) return { stand: s };
      const zeitpunkt = antwortZeitpunkt(s, aktion.zeit, k.jetzt, k.toleranzMs ?? 0);
      return { stand: game.antworten(s, frage, aktion.index, zeitpunkt, k.spieler ?? s.aktiverSpieler) };
    }
    case 'zeitPruefen': {
      const frage = aktuelleFrage(s, k.pool);
      // Mit Toleranz: Antworten, die noch unterwegs sind, sollen nicht verloren gehen
      return { stand: frage ? game.pruefeTimeout(s, frage, k.jetzt - (k.toleranzMs ?? 0)) : s };
    }
    case 'weiter':
      return { stand: game.weiter(s) };
    case 'zwischenstandWeiter':
      return { stand: game.zwischenstandWeiter(s) };
    case 'nochmals':
      return { stand: game.nochmals(s) };
    case 'beenden':
      return { stand: game.beenden(s) };
  }
}
