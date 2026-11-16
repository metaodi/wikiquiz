/**
 * Übertragungsweg für Aktionen und Spielstände (siehe docs/ARCHITEKTUR.md):
 * - `lokalerKanal`: ein Gerät, Pass-and-Play
 * - `broadcastKanal`: mehrere Tabs im selben Browser (für E2E-Tests und Entwicklung, `?kanal=tabs`)
 * - `netzKanal`: mehrere Geräte über WebRTC (Trystero, Verbindungsaufbau über öffentliche Nostr-Relays)
 */
import type { Aktion } from './aktionen';
import type { Teilnehmer } from './raum';
import { hatTurn, turnServerLaden } from './turn';
import type { ProKategorie, Schwierigkeit, Spielstand } from './types';

/** Zustand der Verbindung (nur Netz), für die Diagnose-Anzeige */
export interface NetzStatus {
  /** Verbundene Relays (Verbindungsaufbau) von `relaysGesamt` */
  relays: number;
  relaysGesamt: number;
  /** Direkt verbundene andere Geräte */
  geraete: number;
  /** TURN: nicht eingerichtet, Zugangsdaten werden geladen, bereit, oder Laden gescheitert */
  turn: 'aus' | 'laedt' | 'bereit' | 'fehler';
  /** Läuft mindestens eine Verbindung über den TURN-Server? (null = unbekannt) */
  ueberTurn: boolean | null;
  /** Letzte Fehlermeldung von Trystero, z. B. „peer-connect-failed“ */
  fehler: string | null;
}

/** Jede Nachricht trägt die ID des sendenden Geräts (`von`). */
export type Nachricht =
  /** Gerät → Host: Spielzug ausführen */
  | { typ: 'aktion'; von: string; aktion: Aktion }
  /**
   * Host → alle: aktueller Stand (`stand: null` = Lobby). `jetzt` = Uhrzeit des Hosts beim Senden: Daraus schätzen
   * die Gäste den Unterschied ihrer Uhr zum Host (für Timer-Anzeige und Antwortzeit).
   */
  | {
      typ: 'stand';
      von: string;
      stand: Spielstand | null;
      teilnehmer: Teilnehmer[];
      meldung: string | null;
      jetzt: number;
    }
  /** Gast → Host: beitreten bzw. nach Neuladen wieder anmelden; `fragen` = Kennung des Fragenstands */
  | { typ: 'hallo'; von: string; name: string; fragen: string; schwierigkeit?: Schwierigkeit; proKategorie?: ProKategorie }
  /** Gast verlässt den Raum bzw. Host schliesst ihn */
  | { typ: 'tschuess'; von: string }
  /** Host → ein Gast: Beitritt abgelehnt */
  | { typ: 'abgelehnt'; von: string; an: string; grund: string };

export interface Kanal {
  /** Schickt die Nachricht an alle – auch an die Empfänger auf diesem Gerät. */
  senden(n: Nachricht): void;
  /** Meldet einen Empfänger an; die Rückgabe meldet ihn wieder ab. */
  beiEmpfang(fn: (n: Nachricht) => void): () => void;
  /**
   * Meldet, wenn sich die Zahl der verbundenen anderen Geräte ändert (nur Netz). Kommt ein Gerät dazu – neu oder nach
   * einem Verbindungsabbruch –, schickt der Host ihm so den aktuellen Stand.
   */
  beiVerbindung?(fn: (anzahl: number, neu: boolean) => void): () => void;
  /** Meldet Änderungen am Verbindungszustand (nur Netz, für die Diagnose) */
  beiStatus?(fn: (s: NetzStatus) => void): () => void;
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

/** Namensraum bei Trystero; zusammen mit dem Raumcode ergibt sich der Raum */
export const NETZ_APP_ID = 'github.com/metaodi/wikiquiz';

/**
 * Mehrere Geräte über WebRTC. Trystero wird erst hier geladen (eigener Chunk), das Spiel auf einem Gerät bleibt klein.
 * Bis dahin gesendete Nachrichten werden nachgereicht. Das Passwort (aus dem Code) verschlüsselt den
 * Verbindungsaufbau über die Relays; die Datenkanäle selbst sind durch WebRTC verschlüsselt.
 */
export function netzKanal(code: string): Kanal {
  const v = verteiler();
  let verbindungsEmpfaenger: ((anzahl: number, neu: boolean) => void)[] = [];
  let offen = true;
  let warteschlange: string[] = [];
  let senden: ((json: string) => Promise<void>) | null = null;
  let letzterVersand: Promise<unknown> = Promise.resolve();
  let verlassen: (() => Promise<void>) | null = null;
  let anzahl = 0;
  let statusEmpfaenger: ((s: NetzStatus) => void)[] = [];
  let status: NetzStatus = {
    relays: 0,
    relaysGesamt: 0,
    geraete: 0,
    turn: import.meta.env.VITE_TURN_CREDENTIALS_URL ? 'laedt' : 'aus',
    ueberTurn: null,
    fehler: null,
  };
  let statusTimer: ReturnType<typeof setInterval> | undefined;

  const melden = (neu: boolean) => {
    for (const fn of [...verbindungsEmpfaenger]) fn(anzahl, neu);
    statusSetzen({ geraete: anzahl });
  };

  function statusSetzen(teil: Partial<NetzStatus>) {
    const neu = { ...status, ...teil };
    if (JSON.stringify(neu) === JSON.stringify(status)) return;
    status = neu;
    for (const fn of [...statusEmpfaenger]) fn(status);
  }

  void Promise.all([import('trystero'), turnServerLaden()])
    .then(([{ joinRoom, getRelaySockets }, turnServer]) => {
      if (!offen) return;
      if (status.turn === 'laedt') statusSetzen({ turn: hatTurn(turnServer) ? 'bereit' : 'fehler' });
      // identity 'none': keine dauerhafte Trystero-Identität; die Geräte-ID der App genügt.
      // turnConfig ergänzt die STUN-Server von Trystero um den TURN-Server (falls eingerichtet).
      const room = joinRoom(
        {
          appId: NETZ_APP_ID,
          password: `wikiquiz:${code}`,
          identity: 'none',
          ...(turnServer.length > 0 ? { turnConfig: turnServer } : {}),
        },
        code,
      );
      const aktion = room.makeAction<string>('wikiquiz');
      aktion.onMessage((json) => {
        try {
          v.zustellen(JSON.parse(json) as Nachricht);
        } catch {
          /* fremde oder kaputte Nachricht ignorieren */
        }
      });
      room.onPeerJoin(() => {
        anzahl = Object.keys(room.getPeers()).length;
        melden(true);
      });
      room.onPeerLeave(() => {
        anzahl = Object.keys(room.getPeers()).length;
        melden(false);
      });
      room.onError((e) => {
        console.warn('WikiQuiz: Verbindungsproblem', e);
        statusSetzen({ fehler: e.code });
      });
      // Relays und Verbindungsart regelmässig abfragen (es gibt dafür keine Ereignisse)
      const abfragen = async () => {
        const sockets = Object.values(getRelaySockets());
        const peers = Object.values(room.getPeers());
        const arten = await Promise.all(peers.map((p) => (p.connection ? ueberRelay(p.connection) : null)));
        const bekannt = arten.filter((a): a is boolean => a !== null);
        statusSetzen({
          relays: sockets.filter((w) => w.readyState === WebSocket.OPEN).length,
          relaysGesamt: sockets.length,
          ueberTurn: bekannt.length > 0 ? bekannt.some(Boolean) : null,
          ...(peers.length > 0 ? { fehler: null } : {}),
        });
      };
      void abfragen();
      statusTimer = setInterval(() => void abfragen(), 2000);
      senden = (json) => aktion.send(json);
      verlassen = () => room.leave();
      for (const json of warteschlange) letzterVersand = senden(json).catch(() => undefined);
      warteschlange = [];
    })
    .catch((e: unknown) => console.warn('WikiQuiz: Netzwerk-Modul nicht ladbar', e));

  return {
    senden(n) {
      const json = JSON.stringify(n);
      if (senden) letzterVersand = senden(json).catch(() => undefined);
      else warteschlange.push(json);
      v.zustellen(JSON.parse(json) as Nachricht);
    },
    beiEmpfang: v.anmelden,
    beiStatus(fn) {
      statusEmpfaenger.push(fn);
      fn(status);
      return () => {
        statusEmpfaenger = statusEmpfaenger.filter((f) => f !== fn);
      };
    },
    beiVerbindung(fn) {
      verbindungsEmpfaenger.push(fn);
      return () => {
        verbindungsEmpfaenger = verbindungsEmpfaenger.filter((f) => f !== fn);
      };
    },
    schliessen() {
      offen = false;
      v.leeren();
      verbindungsEmpfaenger = [];
      statusEmpfaenger = [];
      clearInterval(statusTimer);
      // Zuletzt gesendete Nachricht (z. B. „tschuess“) noch zustellen, dann den Raum verlassen
      const weg = verlassen;
      void letzterVersand.finally(() => weg?.());
    },
  };
}

/** Läuft die Verbindung über einen TURN-Server? (gewähltes Kandidatenpaar mit Typ „relay“; null = unbekannt) */
async function ueberRelay(pc: RTCPeerConnection): Promise<boolean | null> {
  try {
    const stats = await pc.getStats();
    let paar: { localCandidateId?: string; remoteCandidateId?: string } | undefined;
    stats.forEach((r) => {
      if (r.type === 'transport' && r.selectedCandidatePairId) paar = stats.get(r.selectedCandidatePairId);
    });
    // Firefox kennt kein selectedCandidatePairId, markiert das Paar aber mit `selected`
    if (!paar) stats.forEach((r) => {
      if (r.type === 'candidate-pair' && (r.selected || (r.nominated && r.state === 'succeeded'))) paar ??= r;
    });
    if (!paar) return null;
    const lokal = stats.get(paar.localCandidateId ?? '');
    const fern = stats.get(paar.remoteCandidateId ?? '');
    return lokal?.candidateType === 'relay' || fern?.candidateType === 'relay';
  } catch {
    return null;
  }
}
