/**
 * Übertragungsweg für Aktionen und Spielstände (siehe docs/ARCHITEKTUR.md):
 * - `lokalerKanal`: ein Gerät, Pass-and-Play
 * - `broadcastKanal`: mehrere Tabs im selben Browser (Vorstufe für WebRTC, ideal für E2E-Tests)
 */
import type { Aktion } from './aktionen';
import type { Teilnehmer } from './raum';
import type { Spielstand } from './types';

/** Jede Nachricht trägt die ID des sendenden Geräts (`von`). */
export type Nachricht =
  /** Gerät → Host: Spielzug ausführen */
  | { typ: 'aktion'; von: string; aktion: Aktion }
  /** Host → alle: aktueller Stand (`stand: null` = Lobby) */
  | { typ: 'stand'; von: string; stand: Spielstand | null; teilnehmer: Teilnehmer[]; meldung: string | null }
  /** Gast → Host: beitreten bzw. nach Neuladen wieder anmelden */
  | { typ: 'hallo'; von: string; name: string }
  /** Gast verlässt den Raum bzw. Host schliesst ihn */
  | { typ: 'tschuess'; von: string }
  /** Host → ein Gast: Beitritt abgelehnt */
  | { typ: 'abgelehnt'; von: string; an: string; grund: string };

export interface Kanal {
  /** Schickt die Nachricht an alle – auch an die Empfänger auf diesem Gerät. */
  senden(n: Nachricht): void;
  /** Meldet einen Empfänger an; die Rückgabe meldet ihn wieder ab. */
  beiEmpfang(fn: (n: Nachricht) => void): () => void;
  schliessen(): void;
}

type Empfaenger = (n: Nachricht) => void;

function verteiler() {
  let empfaenger: Empfaenger[] = [];
  return {
    zustellen(n: Nachricht) {
      // Kopie, falls ein Empfänger sich während der Zustellung ab- oder anmeldet
      for (const fn of [...empfaenger]) fn(n);
    },
    anmelden(fn: Empfaenger) {
      empfaenger.push(fn);
      return () => {
        empfaenger = empfaenger.filter((f) => f !== fn);
      };
    },
    leeren() {
      empfaenger = [];
    },
  };
}

/** Ein Gerät spielt mit sich selbst: Nachrichten gehen sofort (synchron) an alle Empfänger zurück. */
export function lokalerKanal(): Kanal {
  const v = verteiler();
  return { senden: v.zustellen, beiEmpfang: v.anmelden, schliessen: v.leeren };
}

export const KANAL_PRAEFIX = 'wikiquiz:raum:';

/**
 * Tabs im selben Browser. Nachrichten gehen als JSON über den `BroadcastChannel` (der Absender
 * erhält sie dort nicht) und zusätzlich sofort an die eigenen Empfänger – wie bei einem Netzwerk,
 * in dem jeder alles hört. Als JSON, weil Svelte-Zustände (Proxies) nicht direkt übertragbar sind.
 */
export function broadcastKanal(code: string): Kanal {
  const v = verteiler();
  const bc = new BroadcastChannel(KANAL_PRAEFIX + code);
  bc.onmessage = (e: MessageEvent) => {
    try {
      v.zustellen(JSON.parse(e.data as string) as Nachricht);
    } catch {
      /* fremde oder kaputte Nachricht ignorieren */
    }
  };
  return {
    senden(n) {
      const json = JSON.stringify(n);
      bc.postMessage(json);
      v.zustellen(JSON.parse(json) as Nachricht);
    },
    beiEmpfang: v.anmelden,
    schliessen() {
      v.leeren();
      bc.close();
    },
  };
}
