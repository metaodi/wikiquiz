/**
 * TURN-Server für WebRTC (siehe docs/ARCHITEKTUR.md, „Mehrere Geräte“). Ohne TURN scheitert die direkte Verbindung,
 * sobald ein Gerät hinter strengem NAT sitzt (fast alle Handys im Mobilfunknetz). Dann leitet der TURN-Server weiter.
 *
 * Die Zugangsdaten holt die App beim Eröffnen/Beitreten von einer URL, die beim Build gesetzt wird
 * (`VITE_TURN_CREDENTIALS_URL`, z. B. Metered: `https://<app>.metered.live/api/v1/turn/credentials?apiKey=…`).
 * Erwartet wird eine Liste im Format von `RTCIceServer` ({ urls, username?, credential? }).
 * Ohne URL oder bei einem Fehler spielt die App ohne TURN weiter (wie bisher).
 */

export interface IceServer {
  urls: string | string[];
  username?: string;
  credential?: string;
}

/** Wie lange auf die Zugangsdaten gewartet wird, bevor ohne TURN verbunden wird */
export const TURN_TIMEOUT_MS = 5000;

const istText = (x: unknown): x is string => typeof x === 'string' && x.length > 0;

/** Antwort des Anbieters prüfen: nur gültige Einträge mit stun:/turn:/turns:-URLs übernehmen */
export function iceServerPruefen(daten: unknown): IceServer[] {
  const liste = Array.isArray(daten) ? daten : (daten as { iceServers?: unknown } | null)?.iceServers;
  if (!Array.isArray(liste)) return [];
  const res: IceServer[] = [];
  for (const e of liste) {
    if (!e || typeof e !== 'object') continue;
    const { urls, username, credential } = e as Record<string, unknown>;
    const alle = (Array.isArray(urls) ? urls : [urls]).filter(istText).filter((u) => /^(stun|turns?):/i.test(u));
    if (alle.length === 0) continue;
    res.push({
      urls: Array.isArray(urls) ? alle : alle[0],
      ...(istText(username) ? { username } : {}),
      ...(istText(credential) ? { credential } : {}),
    });
  }
  return res;
}

/** Enthält die Liste einen TURN-Server (nicht nur STUN)? */
export function hatTurn(server: IceServer[]): boolean {
  return server.some((s) => (Array.isArray(s.urls) ? s.urls : [s.urls]).some((u) => /^turns?:/i.test(u)));
}

let geladen: IceServer[] | null = null;

/**
 * Zugangsdaten laden (einmal pro Seitenaufruf, bei Erfolg zwischengespeichert). Gibt nie einen Fehler zurück:
 * ohne URL, bei Zeitüberschreitung oder ungültiger Antwort → leere Liste.
 */
export async function turnServerLaden(
  url: string | undefined = import.meta.env.VITE_TURN_CREDENTIALS_URL,
  holen: typeof fetch = (...a) => fetch(...a),
  timeoutMs = TURN_TIMEOUT_MS,
): Promise<IceServer[]> {
  if (!url) return [];
  if (geladen) return geladen;
  const abbruch = new AbortController();
  const timer = setTimeout(() => abbruch.abort(), timeoutMs);
  try {
    const res = await holen(url, { signal: abbruch.signal, cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const server = iceServerPruefen(await res.json());
    if (server.length > 0) geladen = server;
    return server;
  } catch (e) {
    console.warn('WikiQuiz: TURN-Zugangsdaten nicht ladbar, verbinde ohne TURN', e);
    return [];
  } finally {
    clearTimeout(timer);
  }
}

/** Nur für Tests */
export function turnCacheLeeren(): void {
  geladen = null;
}
