import { describe, expect, it } from 'vitest';
import { aktionAnwenden, antwortZeitpunkt } from '../src/lib/aktionen';
import { NETZ_TOLERANZ_S, punkteFuerZeit, ZEITLIMIT_S } from '../src/lib/config';
import { kategorieWaehlen, neuesSpiel, timerStarten } from '../src/lib/game';
import { poolKennung } from '../src/lib/pool';
import { beitreten } from '../src/lib/raum';
import type { Frage, Spielstand } from '../src/lib/types';

function frage(id: string): Frage {
  return {
    id, kategorie: 'geografie', frage: `Frage ${id}?`, antworten: ['A', 'B', 'C', 'D'], korrekt_index: 2,
    schwierigkeit: 1, quelle_typ: 'wikidata', quelle_url: `https://de.wikipedia.org/wiki/${id}`, lizenz: 'CC0',
  };
}
const POOL = [frage('g1'), frage('g2')];
const TOL = NETZ_TOLERANZ_S * 1000;
const START = 1_000_000;

/** Ein Spieler, Frage läuft seit START */
function frageLaeuft(): Spielstand {
  const r = kategorieWaehlen(neuesSpiel([{ name: 'A', farbe: '#000' }], 5), POOL, 'geografie', [], () => 0);
  if (!r.ok) throw new Error(r.grund);
  return timerStarten(r.stand, START);
}

describe('poolKennung', () => {
  it('ist für gleiche Fragen gleich und ändert sich mit IDs, Reihenfolge und Anzahl', () => {
    const k = poolKennung({ fragen: POOL });
    expect(k).toBe(poolKennung({ fragen: [frage('g1'), frage('g2')] }));
    expect(k).toMatch(/^2-[0-9a-f]+$/);
    expect(poolKennung({ fragen: [frage('g2'), frage('g1')] })).not.toBe(k);
    expect(poolKennung({ fragen: [frage('g1'), frage('g3')] })).not.toBe(k);
    expect(poolKennung({ fragen: [frage('g1g2')] })).not.toBe(poolKennung({ fragen: [frage('g1'), frage('g2')] }));
  });
});

describe('antwortZeitpunkt (Antwortzeit vom Gerät gemessen)', () => {
  const s = frageLaeuft();
  it('ohne gemeldete Zeit zählt der Eingang beim Host', () => {
    expect(antwortZeitpunkt(s, undefined, START + 5000, TOL)).toBe(START + 5000);
  });
  it('übernimmt die gemeldete Zeit innerhalb der Toleranz', () => {
    expect(antwortZeitpunkt(s, 4.2, START + 5000, TOL)).toBe(START + 4200);
  });
  it('höchstens die Toleranz schneller als beim Host gemessen', () => {
    expect(antwortZeitpunkt(s, 0.5, START + 5000, TOL)).toBe(START + 5000 - TOL);
  });
  it('nie später als der Eingang; ungültige Werte werden ignoriert', () => {
    expect(antwortZeitpunkt(s, 9, START + 5000, TOL)).toBe(START + 5000);
    expect(antwortZeitpunkt(s, Number.NaN, START + 5000, TOL)).toBe(START + 5000);
    expect(antwortZeitpunkt(s, -3, START + 5000, 10_000)).toBe(START);
  });
});

describe('Antworten und Timeout mit Toleranz', () => {
  const k = (jetzt: number) => ({ pool: POOL, history: [], jetzt, toleranzMs: TOL });

  it('Punkte nach der gemeldeten Zeit', () => {
    const r = aktionAnwenden(frageLaeuft(), { typ: 'antworten', index: 2, zeit: 3 }, k(START + 3800));
    expect(r.stand.zug?.punkte).toBe(punkteFuerZeit(3));
  });

  it('eine knapp vor Ablauf gegebene, verspätet eintreffende Antwort zählt noch', () => {
    const ankunft = START + ZEITLIMIT_S * 1000 + 800;
    const r = aktionAnwenden(frageLaeuft(), { typ: 'antworten', index: 2, zeit: 14.9 }, k(ankunft));
    expect(r.stand.zug?.richtig).toBe(true);
  });

  it('Timeout erst nach Zeitlimit plus Toleranz', () => {
    const knapp = aktionAnwenden(frageLaeuft(), { typ: 'zeitPruefen' }, k(START + ZEITLIMIT_S * 1000 + TOL - 10));
    expect(knapp.stand.phase).toBe('frage');
    const spaeter = aktionAnwenden(frageLaeuft(), { typ: 'zeitPruefen' }, k(START + ZEITLIMIT_S * 1000 + TOL + 10));
    expect(spaeter.stand.phase).toBe('feedback');
  });
});

describe('Beitritt mit anderem Fragenstand', () => {
  it('wird abgelehnt – auch für bekannte Geräte', () => {
    const t = [{ geraet: 'g', name: 'Ben', farbe: '#000' }];
    expect(beitreten(t, 'neu', 'Cleo', false, false)).toEqual({ ok: false, fehler: 'fragen' });
    expect(beitreten(t, 'g', 'Ben', true, false)).toEqual({ ok: false, fehler: 'fragen' });
  });
});
