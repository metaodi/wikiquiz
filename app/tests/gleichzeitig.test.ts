import { describe, expect, it } from 'vitest';
import { punkteFuerZeit, ZEITLIMIT_S } from '../src/lib/config';
import {
  antworten,
  einstellungenPruefen,
  kategorieWaehlen,
  neuesSpiel,
  nochmals,
  pruefeTimeout,
  timerStarten,
  weiter,
  wiederherstellen,
} from '../src/lib/game';
import { ALLE, darf, HOST, zustaendig, type Teilnehmer } from '../src/lib/raum';
import type { Frage, Spielstand } from '../src/lib/types';

function frage(id: string): Frage {
  return {
    id, kategorie: 'geografie', frage: `Frage ${id}?`, antworten: ['A', 'B', 'C', 'D'], korrekt_index: 2,
    schwierigkeit: 1, quelle_typ: 'wikidata', quelle_url: `https://de.wikipedia.org/wiki/${id}`, lizenz: 'CC0',
  };
}
const POOL = [frage('g1'), frage('g2'), frage('g3')];
const rng = () => 0;
const SPIELER = [
  { name: 'Anna', farbe: '#f00' },
  { name: 'Ben', farbe: '#0f0' },
  { name: 'Cleo', farbe: '#00f' },
];

function dreiGleichzeitig(runden = 2): Spielstand {
  return neuesSpiel(SPIELER, runden, { ablauf: 'gleichzeitig' });
}

/** Kategorie wählen und Timer bei t = 0 starten */
function frageLaeuft(s: Spielstand): Spielstand {
  const r = kategorieWaehlen(s, POOL, 'geografie', [], rng);
  if (!r.ok) throw new Error(r.grund);
  return timerStarten(r.stand, 0);
}

describe('Alle gleichzeitig', () => {
  it('startet ohne Übergabe mit der Kategoriewahl; „Vorgänger wählt“ wird zu „selbst“', () => {
    const s = neuesSpiel(SPIELER, 5, { ablauf: 'gleichzeitig', modus: 'vorgaenger' });
    expect(s.phase).toBe('kategorie');
    expect(s.modus).toBe('selbst');
    expect(einstellungenPruefen({}, 3).ablauf).toBe('reihum');
  });

  it('sammelt die Antworten aller; Feedback erst, wenn alle geantwortet haben', () => {
    let s = frageLaeuft(dreiGleichzeitig());
    expect(s.zug?.alle).toEqual([null, null, null]);
    s = antworten(s, POOL[0], 2, 3000, 1); // Ben richtig nach 3 s
    s = antworten(s, POOL[0], 0, 4000, 0); // Anna falsch
    expect(s.phase).toBe('frage');
    // Doppelte Antwort zählt nicht
    expect(antworten(s, POOL[0], 2, 4500, 1)).toBe(s);
    expect(s.spieler.map((p) => p.punkte)).toEqual([0, 0, 0]); // Punkte erst im Feedback
    s = antworten(s, POOL[0], 2, 6000, 2); // Cleo richtig nach 6 s
    expect(s.phase).toBe('feedback');
    expect(s.zug?.alle?.map((a) => a?.punkte)).toEqual([0, punkteFuerZeit(3), punkteFuerZeit(6)]);
    expect(s.spieler.map((p) => p.punkte)).toEqual([0, punkteFuerZeit(3), punkteFuerZeit(6)]);
  });

  it('nach Ablauf der Zeit zählen fehlende Antworten als Timeout', () => {
    let s = frageLaeuft(dreiGleichzeitig());
    s = antworten(s, POOL[0], 2, 1000, 0);
    expect(pruefeTimeout(s, POOL[0], 5000)).toBe(s);
    s = pruefeTimeout(s, POOL[0], ZEITLIMIT_S * 1000 + 1);
    expect(s.phase).toBe('feedback');
    expect(s.zug?.alle?.[1]).toEqual({ gewaehlt: null, zeit: ZEITLIMIT_S, punkte: 0, richtig: false });
    expect(s.spieler[0].punkte).toBe(punkteFuerZeit(1));
  });

  it('eine Runde = eine Frage; die Kategorie wählt reihum der Nächste; kein Zwischenstand', () => {
    let s = frageLaeuft(dreiGleichzeitig(2));
    s = pruefeTimeout(s, POOL[0], 20_000);
    s = weiter(s);
    expect(s.phase).toBe('kategorie');
    expect(s.runde).toBe(2);
    expect(s.aktiverSpieler).toBe(1);
    s = pruefeTimeout(frageLaeuft(s), POOL[1], 40_000);
    expect(weiter(s).phase).toBe('rangliste');
  });

  it('Neuladen mitten in der Frage behält die Antworten; „Nochmals“ behält den Ablauf', () => {
    const s = antworten(frageLaeuft(dreiGleichzeitig()), POOL[0], 2, 1000, 2);
    const w = wiederherstellen(JSON.parse(JSON.stringify(s)), POOL, 2000);
    expect(w.zug?.alle?.[2]?.richtig).toBe(true);
    expect(w.phase).toBe('frage');
    expect(nochmals(s).ablauf).toBe('gleichzeitig');
  });

  it('alte Spielstände ohne Ablauf gelten als „reihum“', () => {
    const { ablauf: _, ...alt } = neuesSpiel(SPIELER, 5);
    expect(wiederherstellen(alt as Spielstand, POOL, 0).ablauf).toBe('reihum');
  });

  it('Zuständigkeit: Frage alle, Feedback der Host', () => {
    const T: Teilnehmer[] = SPIELER.map((p, i) => ({ ...p, geraet: `g${i}` }));
    const s = frageLaeuft(dreiGleichzeitig());
    expect(zustaendig(s)).toBe(ALLE);
    expect(darf(s, T, 'g0', 'g2', { typ: 'antworten', index: 0 })).toBe(true);
    expect(darf(s, T, 'g0', 'fremd', { typ: 'antworten', index: 0 })).toBe(false);
    const fb = pruefeTimeout(s, POOL[0], 20_000);
    expect(zustaendig(fb)).toBe(HOST);
    expect(darf(fb, T, 'g0', 'g1', { typ: 'weiter' })).toBe(false);
    expect(zustaendig({ ...fb, phase: 'kategorie', aktiverSpieler: 2 })).toBe(2);
  });
});
