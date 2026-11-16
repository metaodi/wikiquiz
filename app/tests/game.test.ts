import { describe, expect, it } from 'vitest';
import { punkteFuerZeit, ZEITLIMIT_S } from '../src/lib/config';
import {
  ALLE_KATEGORIEN,
  neueKategorienErgaenzen,
  antworten,
  bereit,
  einstellungenPruefen,
  kategorieWaehlen,
  neuesSpiel,
  nochmals,
  pruefeTimeout,
  rangliste,
  timerStarten,
  waehler,
  weiter,
  wiederherstellen,
  zufallFertig,
  zwischenstandWeiter,
} from '../src/lib/game';
import { waehleFrage } from '../src/lib/picker';
import type { Frage, KategorieId, Spielstand } from '../src/lib/types';

function frage(id: string, kategorie: KategorieId = 'geografie'): Frage {
  return {
    id, kategorie, frage: `Frage ${id}?`, antworten: ['A', 'B', 'C', 'D'], korrekt_index: 2,
    schwierigkeit: 1, quelle_typ: 'wikidata', quelle_url: 'https://de.wikipedia.org/wiki/X', lizenz: 'CC0',
  };
}

const POOL = [frage('g1'), frage('g2'), frage('g3'), frage('k1', 'kunst')];
const rng = () => 0;

function zweiSpieler(runden = 2): Spielstand {
  return neuesSpiel([{ name: ' Anna ', farbe: '#f00' }, { name: 'Ben', farbe: '#00f' }], runden);
}

function zugSpielen(s: Spielstand, idx: number, sek: number, wahl: KategorieId = 'geografie') {
  const r = kategorieWaehlen(s, POOL, wahl, [], rng);
  if (!r.ok) throw new Error(r.grund);
  let t = timerStarten(r.stand, 1000);
  t = antworten(t, r.frage, idx, 1000 + sek * 1000);
  return t;
}

describe('Punkte', () => {
  it('folgt der Formel 100 − 90 × t/15', () => {
    expect(punkteFuerZeit(0)).toBe(100);
    expect(punkteFuerZeit(7.5)).toBe(55);
    expect(punkteFuerZeit(15)).toBe(10);
    expect(punkteFuerZeit(15.01)).toBe(0);
    expect(punkteFuerZeit(-1)).toBe(100);
  });
});

describe('Spielablauf', () => {
  it('startet mit Übergabe bei mehreren Spielern, sonst direkt mit Kategorie', () => {
    expect(zweiSpieler().phase).toBe('uebergabe');
    expect(zweiSpieler().spieler[0].name).toBe('Anna');
    expect(neuesSpiel([{ name: 'Solo', farbe: '#f00' }], 5).phase).toBe('kategorie');
  });

  it('richtige Antwort gibt zeitabhängige Punkte, falsche 0', () => {
    let s = bereit(zweiSpieler());
    s = zugSpielen(s, 2, 3); // richtig nach 3 s
    expect(s.phase).toBe('feedback');
    expect(s.zug!.richtig).toBe(true);
    expect(s.spieler[0].punkte).toBe(punkteFuerZeit(3));
    s = bereit(weiter(s));
    expect(s.aktiverSpieler).toBe(1);
    s = zugSpielen(s, 0, 1); // falsch
    expect(s.zug!.richtig).toBe(false);
    expect(s.spieler[1].punkte).toBe(0);
  });

  it('Antwort nach Ablauf zählt als Timeout', () => {
    const s = zugSpielen(bereit(zweiSpieler()), 2, ZEITLIMIT_S + 1);
    expect(s.zug!.gewaehlt).toBeNull();
    expect(s.spieler[0].punkte).toBe(0);
  });

  it('pruefeTimeout schliesst den Zug nach Ablauf ab', () => {
    const r = kategorieWaehlen(bereit(zweiSpieler()), POOL, 'geografie', [], rng);
    if (!r.ok) throw new Error();
    const s = timerStarten(r.stand, 0);
    expect(pruefeTimeout(s, r.frage, 14_000).phase).toBe('frage');
    const t = pruefeTimeout(s, r.frage, 15_000);
    expect(t.phase).toBe('feedback');
    expect(t.zug!.gewaehlt).toBeNull();
  });

  it('Timer startet nur einmal', () => {
    const r = kategorieWaehlen(bereit(zweiSpieler()), POOL, 'geografie', [], rng);
    if (!r.ok) throw new Error();
    const s = timerStarten(timerStarten(r.stand, 100), 5000);
    expect(s.zug!.timerStart).toBe(100);
  });

  it('Runden: Zwischenstand zwischen Runden, Rangliste am Ende', () => {
    let s = bereit(zweiSpieler(2));
    s = zugSpielen(s, 2, 0);
    s = bereit(weiter(s));
    s = zugSpielen(s, 2, 0);
    s = weiter(s);
    expect(s.phase).toBe('zwischenstand');
    expect(s.runde).toBe(2);
    s = zwischenstandWeiter(s);
    expect(s.phase).toBe('uebergabe');
    expect(s.aktiverSpieler).toBe(0);
    s = zugSpielen(bereit(s), 2, 0, 'kunst');
    s = bereit(weiter(s));
    s = zugSpielen(s, 2, 0);
    expect(weiter(s).phase).toBe('rangliste');
  });

  it('eine Frage wird im Spiel nie doppelt gestellt; erschöpfte Kategorie wird gemeldet', () => {
    let s = neuesSpiel([{ name: 'Solo', farbe: '#f00' }], 15);
    const ids = new Set<string>();
    for (let i = 0; i < 3; i++) {
      const r = kategorieWaehlen(s, POOL, 'geografie', [], Math.random);
      if (!r.ok) throw new Error(r.grund);
      ids.add(r.frage.id);
      s = weiter(antworten(timerStarten(r.stand, 0), r.frage, 0, 1000));
    }
    expect(ids.size).toBe(3);
    expect(kategorieWaehlen(s, POOL, 'geografie', [])).toEqual({ ok: false, grund: 'erschoepft' });
    const z = kategorieWaehlen(s, POOL, 'zufall', [], rng);
    expect(z.ok && z.frage.kategorie).toBe('kunst');
  });

  it('nochmals behält Spieler und setzt Punkte zurück', () => {
    const s = zugSpielen(bereit(zweiSpieler()), 2, 0);
    const n = nochmals(s);
    expect(n.spieler.map((p) => p.name)).toEqual(['Anna', 'Ben']);
    expect(n.spieler.every((p) => p.punkte === 0)).toBe(true);
    expect(n.gestellt).toEqual([]);
  });
});

describe('Rangliste', () => {
  it('teilt Ränge bei Gleichstand', () => {
    const r = rangliste([
      { name: 'A', farbe: '', punkte: 50 },
      { name: 'B', farbe: '', punkte: 80 },
      { name: 'C', farbe: '', punkte: 50 },
      { name: 'D', farbe: '', punkte: 10 },
    ]);
    expect(r.map((p) => [p.spieler.name, p.rang])).toEqual([['B', 1], ['A', 2], ['C', 2], ['D', 4]]);
  });
});

describe('History', () => {
  it('bevorzugt Fragen, die zuletzt nicht gestellt wurden', () => {
    const f = waehleFrage(POOL, 'geografie', [], ['g1', 'g2'], () => 0);
    expect(f!.id).toBe('g3');
  });
  it('nimmt sonst die am längsten zurückliegende', () => {
    const f = waehleFrage(POOL, 'geografie', [], ['g2', 'g3', 'g1'], () => 0);
    expect(f!.id).toBe('g2');
  });
});

describe('Wiederherstellen', () => {
  it('läuft gemäss timerStart weiter und wertet abgelaufene Zeit als Timeout', () => {
    const r = kategorieWaehlen(bereit(zweiSpieler()), POOL, 'geografie', [], rng);
    if (!r.ok) throw new Error();
    const s = timerStarten(r.stand, 0);
    expect(wiederherstellen(s, POOL, 5000).phase).toBe('frage');
    expect(wiederherstellen(s, POOL, 20_000).phase).toBe('feedback');
  });
  it('verwirft den Zug, wenn die Frage nicht mehr im Pool ist', () => {
    const r = kategorieWaehlen(bereit(zweiSpieler()), POOL, 'geografie', [], rng);
    if (!r.ok) throw new Error();
    const s = wiederherstellen(r.stand, [frage('x')], 0);
    expect(s.phase).toBe('kategorie');
    expect(s.zug).toBeNull();
  });
});

describe('Einstellungen', () => {
  it('Standard: selbst wählen, alle Kategorien; ungültige Werte werden ersetzt', () => {
    const s = zweiSpieler();
    expect(s.modus).toBe('selbst');
    expect(s.kategorien).toHaveLength(9);
    expect(einstellungenPruefen({ modus: 'vorgaenger' }, 1).modus).toBe('selbst');
    expect(einstellungenPruefen({ kategorien: [] }, 2).kategorien).toHaveLength(9);
    expect(einstellungenPruefen({ kategorien: ['sport', 'kunst', 'xyz' as KategorieId] }, 2).kategorien).toEqual([
      'kunst',
      'sport',
    ]);
  });

  it('neue Kategorien kommen dazu, wenn früher alle gewählt waren; Allgemeinwissen entfällt', () => {
    const alteSechs = ['naturwissenschaften', 'kunst', 'geschichte', 'sport', 'geografie', 'allgemeinwissen'];
    // Älterer Speicherstand ohne `bekannteKategorien`: alle sechs gewählt → neue ergänzt
    expect(einstellungenPruefen({ kategorien: neueKategorienErgaenzen(alteSechs, undefined) }, 2).kategorien).toEqual(
      ALLE_KATEGORIEN,
    );
    // Nur das entfernte Allgemeinwissen abgewählt → zählt trotzdem als „alle“
    expect(neueKategorienErgaenzen(alteSechs.slice(0, 5), undefined)).toEqual(ALLE_KATEGORIEN);
    // Bewusste Auswahl bleibt, entfernte Kategorie fällt weg
    expect(neueKategorienErgaenzen(['kunst', 'allgemeinwissen'], undefined)).toEqual(['kunst']);
    // Bereits bekannt und abgewählt → bleibt abgewählt
    const ohneStarWars = ALLE_KATEGORIEN.filter((k) => k !== 'starwars');
    expect(neueKategorienErgaenzen(ohneStarWars, ALLE_KATEGORIEN)).toEqual(ohneStarWars);
  });

  it('nur gewählte Kategorien: Zufall lost nur unter diesen, andere sind gesperrt', () => {
    const pool = [frage('g1'), frage('k1', 'kunst'), frage('k2', 'kunst')];
    let s = neuesSpiel([{ name: 'Solo', farbe: '#f00' }], 5, { kategorien: ['kunst'] });
    expect(kategorieWaehlen(s, pool, 'geografie', [], rng).ok).toBe(false);
    for (let i = 0; i < 2; i++) {
      const r = kategorieWaehlen(s, pool, 'zufall', [], () => 0.99);
      if (!r.ok) throw new Error(r.grund);
      expect(r.frage.kategorie).toBe('kunst');
      s = weiter(antworten(timerStarten(zufallFertig(r.stand), 0), r.frage, 0, 0));
    }
    const r = kategorieWaehlen(s, pool, 'zufall', [], rng);
    expect(r.ok ? null : r.grund).toBe('alle_erschoepft');
  });

  it('Immer Zufall: eigene Wahl ist nicht möglich', () => {
    const s = neuesSpiel([{ name: 'Solo', farbe: '#f00' }], 5, { modus: 'zufall' });
    expect(kategorieWaehlen(s, POOL, 'geografie', [], rng).ok).toBe(false);
    const r = kategorieWaehlen(s, POOL, 'zufall', [], rng);
    expect(r.ok && r.stand.phase).toBe('zufall');
  });

  it('Vorheriger Spieler wählt: Wahl vor der Übergabe, danach direkt zur Frage', () => {
    let s = neuesSpiel([{ name: 'A', farbe: '#f00' }, { name: 'B', farbe: '#0f0' }, { name: 'C', farbe: '#00f' }], 2, {
      modus: 'vorgaenger',
    });
    // Erste Frage von A: C (der letzte) wählt
    expect(s.phase).toBe('kategorie');
    expect(waehler(s)).toBe(2);
    let r = kategorieWaehlen(s, POOL, 'kunst', [], rng);
    if (!r.ok) throw new Error(r.grund);
    expect(r.stand.phase).toBe('uebergabe');
    expect(r.stand.zug!.spieler).toBe(0);
    s = bereit(r.stand);
    expect(s.phase).toBe('frage');
    s = weiter(antworten(timerStarten(s, 0), r.frage, 2, 0));
    // A wählt für B, auch per Zufall – die Animation sieht erst B
    expect(s.phase).toBe('kategorie');
    expect(waehler(s)).toBe(0);
    r = kategorieWaehlen(s, POOL, 'zufall', [], rng);
    if (!r.ok) throw new Error(r.grund);
    expect(r.stand.phase).toBe('uebergabe');
    expect(bereit(r.stand).phase).toBe('zufall');
  });

  it('Vorheriger Spieler: nach dem Zwischenstand wählt der Letzte für den Ersten', () => {
    let s = neuesSpiel([{ name: 'A', farbe: '#f00' }, { name: 'B', farbe: '#0f0' }], 2, { modus: 'vorgaenger' });
    for (let i = 0; i < 2; i++) {
      const r = kategorieWaehlen(s, POOL, 'geografie', [], rng);
      if (!r.ok) throw new Error(r.grund);
      s = weiter(antworten(timerStarten(bereit(r.stand), 0), r.frage, 2, 0));
    }
    expect(s.phase).toBe('zwischenstand');
    s = zwischenstandWeiter(s);
    expect(s.phase).toBe('kategorie');
    expect(s.aktiverSpieler).toBe(0);
    expect(waehler(s)).toBe(1);
    expect(nochmals(s).modus).toBe('vorgaenger');
  });

  it('ältere Spielstände ohne Einstellungen werden ergänzt', () => {
    const alt = { ...zweiSpieler() } as Partial<Spielstand>;
    delete alt.modus;
    delete alt.kategorien;
    const s = wiederherstellen(alt as Spielstand, POOL, 0);
    expect(s.modus).toBe('selbst');
    expect(s.kategorien).toHaveLength(9);
  });
});
