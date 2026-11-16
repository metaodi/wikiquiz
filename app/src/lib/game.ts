/**
 * Spiellogik als reine Funktionen: (Spielstand, Eingaben) → neuer Spielstand.
 * Zeit (`jetzt`) und Zufall (`rng`) werden hereingereicht → testbar und reload-fest.
 */
import { ZEITLIMIT_S, punkteFuerZeit } from './config';
import { mischen, stufe, verfuegbareKategorien, waehleFrage, type Rng } from './picker';
import { KATEGORIEN, URSPRUENGLICHE_KATEGORIEN } from './categories';
import type { Einstellungen, Frage, KategorieId, Phase, Schwierigkeit, Spieler, Spielstand } from './types';

export type Wahl = KategorieId | 'zufall';

export const ALLE_KATEGORIEN: KategorieId[] = KATEGORIEN.map((k) => k.id);

export const STANDARD_EINSTELLUNGEN: Einstellungen = { modus: 'selbst', kategorien: ALLE_KATEGORIEN };

/** Ungültige oder fehlende Werte (z. B. aus älteren Spielständen) durch Standardwerte ersetzen. */
export function einstellungenPruefen(e: Partial<Einstellungen> | undefined, anzahlSpieler: number): Einstellungen {
  let modus = e?.modus ?? STANDARD_EINSTELLUNGEN.modus;
  if (!['selbst', 'zufall', 'vorgaenger'].includes(modus)) modus = 'selbst';
  if (modus === 'vorgaenger' && anzahlSpieler < 2) modus = 'selbst';
  // Reihenfolge wie in KATEGORIEN, unbekannte IDs verwerfen
  const gewaehlt = ALLE_KATEGORIEN.filter((id) => e?.kategorien?.includes(id));
  return { modus, kategorien: gewaehlt.length > 0 ? gewaehlt : [...ALLE_KATEGORIEN] };
}

/**
 * Gespeicherte Kategorienauswahl um seither neu hinzugekommene Kategorien ergänzen – aber nur, wenn
 * damals alle bekannten Kategorien gewählt waren (Standard „alle“). Eine bewusste Auswahl bleibt.
 * Ohne `bekannt` (ältere Speicherstände) gelten die ursprünglichen sechs Kategorien als bekannt.
 * Inzwischen entfernte Kategorien (z. B. „allgemeinwissen“) zählen dabei nicht.
 */
export function neueKategorienErgaenzen(
  gewaehlt: string[] | undefined,
  bekannt: string[] | undefined,
): KategorieId[] | undefined {
  if (!gewaehlt) return undefined;
  const alt = bekannt ?? URSPRUENGLICHE_KATEGORIEN;
  const gueltig = ALLE_KATEGORIEN.filter((k) => gewaehlt.includes(k));
  if (!alt.filter((k) => (ALLE_KATEGORIEN as string[]).includes(k)).every((k) => gewaehlt.includes(k))) return gueltig;
  return [...gueltig, ...ALLE_KATEGORIEN.filter((k) => !alt.includes(k) && !gueltig.includes(k))];
}

/** Wählt der vorherige Spieler die Kategorie für den aktiven Spieler? */
export function vorgaengerWaehlt(s: Pick<Spielstand, 'spieler' | 'modus'>): boolean {
  return s.modus === 'vorgaenger' && s.spieler.length > 1;
}

/** Index des Spielers, der die Kategorie für den aktuellen Zug bestimmt */
export function waehler(s: Pick<Spielstand, 'spieler' | 'modus' | 'aktiverSpieler'>): number {
  const n = s.spieler.length;
  return vorgaengerWaehlt(s) ? (s.aktiverSpieler - 1 + n) % n : s.aktiverSpieler;
}

/**
 * Erste Phase eines Zugs. Wählt der Vorgänger, kommt zuerst die Kategoriewahl (das Gerät ist
 * noch bei ihm), danach die Übergabe. Sonst zuerst die Übergabe (ausser bei einem Spieler).
 */
export function startPhase(s: Pick<Spielstand, 'spieler' | 'modus'>): Phase {
  if (vorgaengerWaehlt(s)) return 'kategorie';
  return s.spieler.length > 1 ? 'uebergabe' : 'kategorie';
}

export type NeuerSpieler = Pick<Spieler, 'name' | 'farbe'> & { schwierigkeit?: Schwierigkeit };

export function neuesSpiel(
  spieler: NeuerSpieler[],
  runden: number,
  einstellungen?: Partial<Einstellungen>,
): Spielstand {
  const s: Spielstand = {
    version: 1,
    phase: 'setup',
    spieler: spieler.map((p) => ({ name: p.name.trim(), farbe: p.farbe, punkte: 0, schwierigkeit: stufe(p.schwierigkeit) })),
    runden,
    ...einstellungenPruefen(einstellungen, spieler.length),
    runde: 1,
    aktiverSpieler: 0,
    gestellt: [],
    zug: null,
  };
  return { ...s, phase: startPhase(s) };
}

/** Gleiche Spieler, Punkte zurückgesetzt */
export function nochmals(s: Spielstand): Spielstand {
  return neuesSpiel(s.spieler, s.runden, { modus: s.modus, kategorien: s.kategorien });
}

/** Übergabe bestätigt: Kategorie wählen – oder, falls der Vorgänger schon gewählt hat, direkt zur Frage. */
export function bereit(s: Spielstand): Spielstand {
  if (s.phase !== 'uebergabe') return s;
  if (s.zug) return { ...s, phase: s.zug.zufall ? 'zufall' : 'frage' };
  return { ...s, phase: 'kategorie' };
}

export type WahlErgebnis =
  | { ok: true; stand: Spielstand; frage: Frage }
  | { ok: false; grund: 'erschoepft' | 'alle_erschoepft' };

export function kategorieWaehlen(
  s: Spielstand,
  pool: Frage[],
  wahl: Wahl,
  history: string[],
  rng: Rng = Math.random,
): WahlErgebnis {
  if (s.phase !== 'kategorie') return { ok: false, grund: 'erschoepft' };
  let kategorie: KategorieId;
  if (wahl === 'zufall') {
    const offen = verfuegbareKategorien(pool, s.gestellt, s.kategorien);
    if (offen.length === 0) return { ok: false, grund: 'alle_erschoepft' };
    kategorie = offen[Math.floor(rng() * offen.length)];
  } else {
    if (s.modus === 'zufall' || !s.kategorien.includes(wahl)) return { ok: false, grund: 'erschoepft' };
    kategorie = wahl;
  }
  const frage = waehleFrage(pool, kategorie, s.gestellt, history, rng, s.spieler[s.aktiverSpieler].schwierigkeit);
  if (!frage) return { ok: false, grund: 'erschoepft' };
  return {
    ok: true,
    frage,
    stand: {
      ...s,
      // Hat der Vorgänger gewählt, geht das Gerät jetzt erst an den aktiven Spieler
      phase: vorgaengerWaehlt(s) ? 'uebergabe' : wahl === 'zufall' ? 'zufall' : 'frage',
      gestellt: [...s.gestellt, frage.id],
      zug: {
        spieler: s.aktiverSpieler,
        kategorie,
        zufall: wahl === 'zufall',
        frageId: frage.id,
        reihenfolge: mischen(frage.antworten.map((_, i) => i), rng),
        timerStart: null,
        gewaehlt: null,
        zeit: null,
        punkte: 0,
        richtig: false,
      },
    },
  };
}

export function zufallFertig(s: Spielstand): Spielstand {
  return s.phase === 'zufall' ? { ...s, phase: 'frage' } : s;
}

/** Startet den Timer – nur einmal pro Zug (auch nach Neuladen nicht neu). */
export function timerStarten(s: Spielstand, jetzt: number): Spielstand {
  if (s.phase !== 'frage' || !s.zug || s.zug.timerStart !== null) return s;
  return { ...s, zug: { ...s.zug, timerStart: jetzt } };
}

export function restzeit(s: Spielstand, jetzt: number): number {
  if (!s.zug || s.zug.timerStart === null) return ZEITLIMIT_S;
  return Math.max(0, ZEITLIMIT_S - (jetzt - s.zug.timerStart) / 1000);
}

function zugAbschliessen(s: Spielstand, gewaehlt: number | null, zeit: number, frage: Frage): Spielstand {
  const zug = s.zug!;
  const richtig = gewaehlt !== null && gewaehlt === frage.korrekt_index;
  const punkte = richtig ? punkteFuerZeit(zeit) : 0;
  const spieler = s.spieler.map((p, i) => (i === zug.spieler ? { ...p, punkte: p.punkte + punkte } : p));
  return { ...s, phase: 'feedback', spieler, zug: { ...zug, gewaehlt, zeit, punkte, richtig } };
}

export function antworten(s: Spielstand, frage: Frage, index: number, jetzt: number): Spielstand {
  if (s.phase !== 'frage' || !s.zug || s.zug.timerStart === null) return s;
  const zeit = (jetzt - s.zug.timerStart) / 1000;
  if (zeit > ZEITLIMIT_S) return zugAbschliessen(s, null, ZEITLIMIT_S, frage);
  return zugAbschliessen(s, index, zeit, frage);
}

/** Prüft, ob die Zeit abgelaufen ist (auch nach Neuladen), und schliesst den Zug als Timeout ab. */
export function pruefeTimeout(s: Spielstand, frage: Frage, jetzt: number): Spielstand {
  if (s.phase !== 'frage' || !s.zug || s.zug.timerStart === null) return s;
  if (restzeit(s, jetzt) > 0) return s;
  return zugAbschliessen(s, null, ZEITLIMIT_S, frage);
}

/** Nach dem Feedback: nächster Spieler, ggf. Zwischenstand oder Rangliste. */
export function weiter(s: Spielstand): Spielstand {
  if (s.phase !== 'feedback') return s;
  const naechster = s.aktiverSpieler + 1;
  if (naechster < s.spieler.length) {
    return { ...s, aktiverSpieler: naechster, zug: null, phase: startPhase(s) };
  }
  // Runde abgeschlossen
  if (s.runde >= s.runden) return { ...s, zug: null, phase: 'rangliste' };
  const neu: Spielstand = { ...s, runde: s.runde + 1, aktiverSpieler: 0, zug: null, phase: 'zwischenstand' };
  // Bei einem Spieler zeigt bereits das Feedback den Punktestand
  return s.spieler.length > 1 ? neu : { ...neu, phase: 'kategorie' };
}

export function zwischenstandWeiter(s: Spielstand): Spielstand {
  return s.phase === 'zwischenstand' ? { ...s, phase: startPhase(s) } : s;
}

/** Wenn keine Fragen mehr übrig sind: Spiel vorzeitig beenden. */
export function beenden(s: Spielstand): Spielstand {
  return { ...s, zug: null, phase: 'rangliste' };
}

export interface Platz {
  rang: number;
  spieler: Spieler;
  index: number;
}

/** Rangliste; bei Punktegleichstand teilen sich Spieler den Rang (1, 1, 3). */
export function rangliste(spieler: Spieler[]): Platz[] {
  const sortiert = spieler
    .map((p, index) => ({ spieler: p, index }))
    .sort((a, b) => b.spieler.punkte - a.spieler.punkte || a.index - b.index);
  return sortiert.map((e) => ({
    ...e,
    rang: 1 + sortiert.filter((o) => o.spieler.punkte > e.spieler.punkte).length,
  }));
}

/**
 * Konsistenz nach dem Laden aus localStorage: Frage noch im Pool? Phase gültig?
 * Ist die Frage verschwunden (neuer Pool), wird der Zug verworfen und neu gewählt.
 */
export function wiederherstellen(gespeichert: Spielstand, pool: Frage[], jetzt: number): Spielstand {
  const s: Spielstand = {
    ...gespeichert,
    ...einstellungenPruefen(gespeichert, gespeichert.spieler.length),
    // Spielstände ohne Schwierigkeit (vor Einführung der Wahl) → Standard
    spieler: gespeichert.spieler.map((p) => ({ ...p, schwierigkeit: stufe(p.schwierigkeit) })),
  };
  if (s.phase === 'setup') return s;
  if (s.zug && ['uebergabe', 'zufall', 'frage', 'feedback'].includes(s.phase)) {
    const frage = pool.find((f) => f.id === s.zug!.frageId);
    if (!frage) return { ...s, zug: null, phase: 'kategorie' };
    if (s.phase === 'zufall') return { ...s, phase: 'frage' };
    if (s.phase === 'frage') return pruefeTimeout(s, frage, jetzt);
  }
  return s;
}
