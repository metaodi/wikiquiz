/**
 * Spiellogik als reine Funktionen: (Spielstand, Eingaben) → neuer Spielstand.
 * Zeit (`jetzt`) und Zufall (`rng`) werden hereingereicht → testbar und reload-fest.
 */
import { ZEITLIMIT_S, punkteFuerZeit } from './config';
import { mischen, verfuegbareKategorien, waehleFrage, type Rng } from './picker';
import type { Frage, KategorieId, Phase, Spieler, Spielstand } from './types';

export type Wahl = KategorieId | 'zufall';

export function startPhase(s: Pick<Spielstand, 'spieler'>): Phase {
  return s.spieler.length > 1 ? 'uebergabe' : 'kategorie';
}

export function neuesSpiel(spieler: Omit<Spieler, 'punkte'>[], runden: number): Spielstand {
  const s: Spielstand = {
    version: 1,
    phase: 'setup',
    spieler: spieler.map((p) => ({ name: p.name.trim(), farbe: p.farbe, punkte: 0 })),
    runden,
    runde: 1,
    aktiverSpieler: 0,
    gestellt: [],
    zug: null,
  };
  return { ...s, phase: startPhase(s) };
}

/** Gleiche Spieler, Punkte zurückgesetzt */
export function nochmals(s: Spielstand): Spielstand {
  return neuesSpiel(s.spieler, s.runden);
}

export function bereit(s: Spielstand): Spielstand {
  return s.phase === 'uebergabe' ? { ...s, phase: 'kategorie' } : s;
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
    const offen = verfuegbareKategorien(pool, s.gestellt);
    if (offen.length === 0) return { ok: false, grund: 'alle_erschoepft' };
    kategorie = offen[Math.floor(rng() * offen.length)];
  } else {
    kategorie = wahl;
  }
  const frage = waehleFrage(pool, kategorie, s.gestellt, history, rng);
  if (!frage) return { ok: false, grund: 'erschoepft' };
  return {
    ok: true,
    frage,
    stand: {
      ...s,
      phase: wahl === 'zufall' ? 'zufall' : 'frage',
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
    return { ...s, aktiverSpieler: naechster, zug: null, phase: 'uebergabe' };
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
export function wiederherstellen(s: Spielstand, pool: Frage[], jetzt: number): Spielstand {
  if (s.phase === 'setup') return s;
  if (s.zug && ['zufall', 'frage', 'feedback'].includes(s.phase)) {
    const frage = pool.find((f) => f.id === s.zug!.frageId);
    if (!frage) return { ...s, zug: null, phase: 'kategorie' };
    if (s.phase === 'zufall') return { ...s, phase: 'frage' };
    if (s.phase === 'frage') return pruefeTimeout(s, frage, jetzt);
  }
  return s;
}
