import { describe, expect, it } from 'vitest';
import type { Aktion } from '../src/lib/aktionen';
import { MAX_SPIELER, SPIELER_FARBEN } from '../src/lib/config';
import { neuesSpiel } from '../src/lib/game';
import { broadcastKanal, lokalerKanal, type Nachricht } from '../src/lib/kanal';
import {
  beitreten,
  codeNormalisieren,
  darf,
  HOST,
  verlassen,
  zufallsCode,
  zustaendig,
  type Teilnehmer,
} from '../src/lib/raum';
import type { Spielstand } from '../src/lib/types';

const T: Teilnehmer[] = [
  { geraet: 'h', name: 'Anna', farbe: SPIELER_FARBEN[0] },
  { geraet: 'g1', name: 'Ben', farbe: SPIELER_FARBEN[1] },
  { geraet: 'g2', name: 'Cleo', farbe: SPIELER_FARBEN[2] },
];

function spiel(modus: 'selbst' | 'vorgaenger' = 'selbst'): Spielstand {
  return neuesSpiel(T.map(({ name, farbe }) => ({ name, farbe })), 5, { modus });
}

describe('zustaendig', () => {
  it('ordnet jede Phase dem richtigen Spieler oder dem Host zu', () => {
    const s = { ...spiel(), aktiverSpieler: 1 };
    expect(zustaendig({ ...s, phase: 'uebergabe' })).toBe(1);
    expect(zustaendig({ ...s, phase: 'kategorie' })).toBe(1);
    expect(zustaendig({ ...s, phase: 'frage' })).toBe(1);
    expect(zustaendig({ ...s, phase: 'zwischenstand' })).toBe(HOST);
    expect(zustaendig({ ...s, phase: 'rangliste' })).toBe(HOST);
  });

  it('lässt im Modus „Vorgänger“ den vorherigen Spieler die Kategorie wählen', () => {
    const s = { ...spiel('vorgaenger'), aktiverSpieler: 0, phase: 'kategorie' as const };
    expect(zustaendig(s)).toBe(2);
  });
});

describe('darf', () => {
  const weiter: Aktion = { typ: 'weiter' };
  it('erlaubt Spielzüge nur dem Gerät, das dran ist', () => {
    const s = { ...spiel(), aktiverSpieler: 1, phase: 'uebergabe' as const };
    expect(darf(s, T, 'h', 'g1', { typ: 'bereit' })).toBe(true);
    expect(darf(s, T, 'h', 'g2', { typ: 'bereit' })).toBe(false);
    expect(darf(s, T, 'h', 'h', { typ: 'bereit' })).toBe(false);
  });

  it('Zwischenstand und Rangliste bedient der Host', () => {
    const s = { ...spiel(), phase: 'zwischenstand' as const };
    expect(darf(s, T, 'h', 'h', { typ: 'zwischenstandWeiter' })).toBe(true);
    expect(darf(s, T, 'h', 'g1', { typ: 'zwischenstandWeiter' })).toBe(false);
    expect(darf({ ...s, phase: 'rangliste' }, T, 'h', 'g1', { typ: 'nochmals' })).toBe(false);
    expect(darf({ ...s, phase: 'rangliste' }, T, 'h', 'h', { typ: 'nochmals' })).toBe(true);
    expect(darf(s, T, 'h', 'g1', weiter)).toBe(false);
  });

  it('Zeitablauf darf jeder melden, beenden der Host jederzeit', () => {
    const s = { ...spiel(), aktiverSpieler: 1, phase: 'frage' as const };
    expect(darf(s, T, 'h', 'g2', { typ: 'zeitPruefen' })).toBe(true);
    expect(darf(s, T, 'h', 'h', { typ: 'beenden' })).toBe(true);
    expect(darf(s, T, 'h', 'g2', { typ: 'beenden' })).toBe(false);
  });
});

describe('beitreten', () => {
  it('vergibt die erste freie Farbe und kürzt den Namen', () => {
    const r = beitreten([T[0], T[2]], 'neu', '  Dario ', false);
    expect(r).toEqual({ ok: true, teilnehmer: [T[0], T[2], { geraet: 'neu', name: 'Dario', farbe: SPIELER_FARBEN[1] }] });
  });

  it('erkennt bekannte Geräte wieder, auch während des Spiels', () => {
    expect(beitreten(T, 'g1', 'Anderer Name', true)).toEqual({ ok: true, teilnehmer: T });
  });

  it('lehnt ab: Spiel läuft, Raum voll, Name vergeben', () => {
    expect(beitreten(T, 'neu', 'Dario', true)).toEqual({ ok: false, fehler: 'laeuft' });
    const voll = Array.from({ length: MAX_SPIELER }, (_, i) => ({ geraet: `x${i}`, name: `S${i}`, farbe: '#000' }));
    expect(beitreten(voll, 'neu', 'Dario', false)).toEqual({ ok: false, fehler: 'voll' });
    expect(beitreten(T, 'neu', 'ben', false)).toEqual({ ok: false, fehler: 'name' });
  });

  it('verlassen entfernt das Gerät', () => {
    expect(verlassen(T, 'g1').map((t) => t.name)).toEqual(['Anna', 'Cleo']);
  });
});

describe('Raumcode', () => {
  it('ist 4 Zeichen lang, ohne verwechselbare Zeichen', () => {
    let i = 0;
    const rng = () => (i++ % 10) / 10;
    const code = zufallsCode(rng);
    expect(code).toMatch(/^[A-HJ-NP-Z2-9]{4}$/);
  });

  it('Eingabe wird vereinheitlicht', () => {
    expect(codeNormalisieren(' ab-c d ')).toBe('ABCD');
  });
});

describe('Kanäle', () => {
  const weiter: Nachricht = { typ: 'aktion', von: 'a', aktion: { typ: 'weiter' } };

  it('lokalerKanal stellt synchron an alle Empfänger zu, abmelden und schliessen wirken', () => {
    const k = lokalerKanal();
    const a: Nachricht[] = [];
    const b: Nachricht[] = [];
    const ab = k.beiEmpfang((n) => a.push(n));
    k.beiEmpfang((n) => b.push(n));
    k.senden(weiter);
    expect(a).toEqual([weiter]);
    expect(b).toEqual([weiter]);
    ab();
    k.senden(weiter);
    expect(a).toHaveLength(1);
    expect(b).toHaveLength(2);
    k.schliessen();
    k.senden(weiter);
    expect(b).toHaveLength(2);
  });

  it('broadcastKanal verbindet zwei Kanäle mit demselben Code (und stellt auch lokal zu)', async () => {
    const code = zufallsCode(Math.random);
    const host = broadcastKanal(code);
    const gast = broadcastKanal(code);
    const fremd = broadcastKanal(code + 'X');
    const beimHost: Nachricht[] = [];
    const beimGast: Nachricht[] = [];
    const beimFremden: Nachricht[] = [];
    host.beiEmpfang((n) => beimHost.push(n));
    gast.beiEmpfang((n) => beimGast.push(n));
    fremd.beiEmpfang((n) => beimFremden.push(n));
    gast.senden(weiter);
    expect(beimGast).toEqual([weiter]);
    await new Promise((r) => setTimeout(r, 50));
    expect(beimHost).toEqual([weiter]);
    expect(beimFremden).toEqual([]);
    host.schliessen();
    gast.schliessen();
    fremd.schliessen();
  });
});
