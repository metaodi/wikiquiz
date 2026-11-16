import { describe, expect, it } from 'vitest';
import { aktionAnwenden, type Aktion, type Kontext } from '../src/lib/aktionen';
import { punkteFuerZeit } from '../src/lib/config';
import { neuesSpiel } from '../src/lib/game';
import type { Frage, KategorieId, Spielstand } from '../src/lib/types';

function frage(id: string, kategorie: KategorieId = 'geografie'): Frage {
  return {
    id, kategorie, frage: `Frage ${id}?`, antworten: ['A', 'B', 'C', 'D'], korrekt_index: 2,
    schwierigkeit: 1, quelle_typ: 'wikidata', quelle_url: `https://de.wikipedia.org/wiki/${id}`, lizenz: 'CC0',
  };
}

const POOL = [frage('g1'), frage('g2'), frage('k1', 'kunst')];

function kontext(jetzt = 0): Kontext {
  return { pool: POOL, history: [], jetzt, rng: () => 0 };
}

function zweiSpieler(runden = 1): Spielstand {
  return neuesSpiel([{ name: 'Anna', farbe: '#f00' }, { name: 'Ben', farbe: '#00f' }], runden);
}

/** Wendet mehrere Aktionen nacheinander an (jeweils mit eigener Uhrzeit) */
function folge(s: Spielstand, schritte: [Aktion, number?][]): Spielstand {
  return schritte.reduce((st, [a, jetzt]) => aktionAnwenden(st, a, kontext(jetzt)).stand, s);
}

describe('aktionAnwenden', () => {
  it('spielt einen ganzen Zug über Aktionen', () => {
    const s = folge(zweiSpieler(), [
      [{ typ: 'bereit' }],
      [{ typ: 'kategorie', wahl: 'geografie' }],
      [{ typ: 'timerStarten' }, 1000],
      [{ typ: 'antworten', index: 2 }, 4000],
    ]);
    expect(s.phase).toBe('feedback');
    expect(s.zug?.richtig).toBe(true);
    expect(s.spieler[0].punkte).toBe(punkteFuerZeit(3));
    const n = aktionAnwenden(s, { typ: 'weiter' }, kontext()).stand;
    expect(n.aktiverSpieler).toBe(1);
    expect(n.phase).toBe('uebergabe');
  });

  it('meldet die neu gezogene Frage für die History', () => {
    const s = aktionAnwenden(zweiSpieler(), { typ: 'bereit' }, kontext()).stand;
    const r = aktionAnwenden(s, { typ: 'kategorie', wahl: 'kunst' }, kontext());
    expect(r.neueFrage?.id).toBe('k1');
    expect(r.stand.zug?.frageId).toBe('k1');
    expect(r.fehler).toBeUndefined();
  });

  it('lässt den Spielstand bei erschöpfter Kategorie unverändert und meldet den Grund', () => {
    const s = { ...aktionAnwenden(zweiSpieler(), { typ: 'bereit' }, kontext()).stand, gestellt: ['k1'] };
    const r = aktionAnwenden(s, { typ: 'kategorie', wahl: 'kunst' }, kontext());
    expect(r.fehler).toBe('erschoepft');
    expect(r.stand).toBe(s);
    expect(r.neueFrage).toBeUndefined();
  });

  it('ignoriert eine doppelte Kategoriewahl ohne Fehlermeldung', () => {
    const s = aktionAnwenden(zweiSpieler(), { typ: 'bereit' }, kontext()).stand;
    const nachWahl = aktionAnwenden(s, { typ: 'kategorie', wahl: 'kunst' }, kontext()).stand;
    const r = aktionAnwenden(nachWahl, { typ: 'kategorie', wahl: 'geografie' }, kontext());
    expect(r.fehler).toBeUndefined();
    expect(r.stand).toBe(nachWahl);
  });

  it('meldet, wenn in keiner Kategorie mehr Fragen übrig sind', () => {
    const s = { ...aktionAnwenden(zweiSpieler(), { typ: 'bereit' }, kontext()).stand, gestellt: ['g1', 'g2', 'k1'] };
    expect(aktionAnwenden(s, { typ: 'kategorie', wahl: 'zufall' }, kontext()).fehler).toBe('alle_erschoepft');
  });

  it('schliesst den Zug nach Ablauf der Zeit als Timeout ab', () => {
    const s = folge(zweiSpieler(), [
      [{ typ: 'bereit' }],
      [{ typ: 'kategorie', wahl: 'geografie' }],
      [{ typ: 'timerStarten' }, 0],
      [{ typ: 'zeitPruefen' }, 60_000],
    ]);
    expect(s.phase).toBe('feedback');
    expect(s.zug?.gewaehlt).toBeNull();
  });

  it('ignoriert Antworten und Zeitprüfung ohne aktuelle Frage', () => {
    const s = zweiSpieler();
    expect(aktionAnwenden(s, { typ: 'antworten', index: 0 }, kontext()).stand).toBe(s);
    expect(aktionAnwenden(s, { typ: 'zeitPruefen' }, kontext()).stand).toBe(s);
  });

  it('beendet das Spiel und startet es mit denselben Spielern neu', () => {
    const ende = aktionAnwenden(zweiSpieler(), { typ: 'beenden' }, kontext()).stand;
    expect(ende.phase).toBe('rangliste');
    const neu = aktionAnwenden({ ...ende, spieler: ende.spieler.map((p) => ({ ...p, punkte: 5 })) },
      { typ: 'nochmals' }, kontext()).stand;
    expect(neu.spieler.map((p) => p.punkte)).toEqual([0, 0]);
    expect(neu.runde).toBe(1);
  });

  it('Aktionen überstehen JSON (Übertragung zwischen Geräten)', () => {
    const a: Aktion = { typ: 'kategorie', wahl: 'zufall' };
    expect(JSON.parse(JSON.stringify(a))).toEqual(a);
  });
});
