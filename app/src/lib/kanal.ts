/**
 * Übertragungsweg für Aktionen und Spielstände. Heute gibt es nur den lokalen Kanal (Pass-and-Play
 * auf einem Gerät); später kommen `BroadcastChannel` und WebRTC dazu (siehe docs/ARCHITEKTUR.md).
 */
import type { Aktion } from './aktionen';
import type { Spielstand } from './types';

export type Nachricht =
  /** Gerät → Host: Spielzug ausführen */
  | { typ: 'aktion'; aktion: Aktion }
  /** Host → alle Geräte: aktueller Spielstand */
  | { typ: 'stand'; stand: Spielstand | null };

export interface Kanal {
  senden(n: Nachricht): void;
  /** Meldet einen Empfänger an; die Rückgabe meldet ihn wieder ab. */
  beiEmpfang(fn: (n: Nachricht) => void): () => void;
  schliessen(): void;
}

/** Ein Gerät spielt mit sich selbst: Nachrichten gehen sofort (synchron) an alle Empfänger zurück. */
export function lokalerKanal(): Kanal {
  let empfaenger: ((n: Nachricht) => void)[] = [];
  return {
    senden(n) {
      // Kopie, falls ein Empfänger sich während der Zustellung ab- oder anmeldet
      for (const fn of [...empfaenger]) fn(n);
    },
    beiEmpfang(fn) {
      empfaenger.push(fn);
      return () => {
        empfaenger = empfaenger.filter((f) => f !== fn);
      };
    },
    schliessen() {
      empfaenger = [];
    },
  };
}
