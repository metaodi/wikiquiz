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
  | { typ: 'antworten'; index: number }
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
}

export interface Ergebnis {
  stand: Spielstand;
  /** Neu gezogene Frage (nur bei `kategorie`), damit das Gerät sie in seiner History vermerken kann */
  neueFrage?: Frage;
  /** Kategoriewahl gescheitert, Spielstand unverändert */
  fehler?: 'erschoepft' | 'alle_erschoepft';
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
      return { stand: frage ? game.antworten(s, frage, aktion.index, k.jetzt) : s };
    }
    case 'zeitPruefen': {
      const frage = aktuelleFrage(s, k.pool);
      return { stand: frage ? game.pruefeTimeout(s, frage, k.jetzt) : s };
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
