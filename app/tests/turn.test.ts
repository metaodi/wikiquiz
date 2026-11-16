import { beforeEach, describe, expect, it, vi } from 'vitest';
import { hatTurn, iceServerPruefen, turnCacheLeeren, turnServerLaden } from '../src/lib/turn';

const METERED = [
  { urls: 'stun:stun.relay.metered.ca:80' },
  { urls: 'turn:global.relay.metered.ca:80', username: 'u', credential: 'p' },
  { urls: 'turns:global.relay.metered.ca:443?transport=tcp', username: 'u', credential: 'p' },
];

const antwort = (daten: unknown, ok = true) => (async () => ({ ok, status: ok ? 200 : 401, json: async () => daten })) as unknown as typeof fetch;

describe('iceServerPruefen', () => {
  it('übernimmt die Antwort von Metered', () => {
    expect(iceServerPruefen(METERED)).toEqual(METERED);
    expect(iceServerPruefen({ iceServers: METERED })).toEqual(METERED);
  });
  it('verwirft ungültige Einträge und fremde URLs', () => {
    expect(
      iceServerPruefen([null, 'x', { urls: 'https://boese.example' }, { urls: ['turn:a', 'javascript:x'], username: 1 }]),
    ).toEqual([{ urls: ['turn:a'] }]);
    expect(iceServerPruefen({ fehler: 'kaputt' })).toEqual([]);
  });
  it('erkennt TURN', () => {
    expect(hatTurn(METERED)).toBe(true);
    expect(hatTurn([{ urls: 'stun:x' }])).toBe(false);
  });
});

describe('turnServerLaden', () => {
  beforeEach(() => {
    turnCacheLeeren();
    vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  it('ohne URL: keine Anfrage, leere Liste', async () => {
    const holen = vi.fn();
    expect(await turnServerLaden('', holen)).toEqual([]);
    expect(holen).not.toHaveBeenCalled();
  });
  it('lädt einmal und merkt sich das Ergebnis', async () => {
    const holen = vi.fn(antwort(METERED));
    expect(await turnServerLaden('https://x.metered.live/api', holen)).toEqual(METERED);
    expect(await turnServerLaden('https://x.metered.live/api', holen)).toEqual(METERED);
    expect(holen).toHaveBeenCalledTimes(1);
  });
  it('bei Fehlern ohne TURN weiter', async () => {
    expect(await turnServerLaden('https://x', antwort({}, false))).toEqual([]);
    expect(await turnServerLaden('https://x', (async () => Promise.reject(new Error('offline'))) as typeof fetch)).toEqual([]);
  });
  it('bricht nach dem Timeout ab', async () => {
    const haengt = ((_: unknown, init?: RequestInit) =>
      new Promise((_r, reject) => init?.signal?.addEventListener('abort', () => reject(new Error('abgebrochen'))))) as typeof fetch;
    expect(await turnServerLaden('https://x', haengt, 10)).toEqual([]);
  });
});
