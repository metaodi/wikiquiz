/** localStorage-Zugriffe, alle in try/catch (privater Modus, gesperrter Speicher …). */
import { HISTORY_MAX } from './config';
import type { Einstellungen, KategorieId, ProKategorie, Schwierigkeit, Spielstand } from './types';

const KEY_SPIEL = 'wikiquiz:game:v1';
const KEY_HISTORY = 'wikiquiz:history:v1';
const KEY_LETZTE_SPIELER = 'wikiquiz:players:v1';

function lesen<T>(key: string): T | null {
  try {
    const roh = localStorage.getItem(key);
    return roh ? (JSON.parse(roh) as T) : null;
  } catch {
    return null;
  }
}

function schreiben(key: string, wert: unknown): void {
  try {
    if (wert === null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(wert));
  } catch {
    /* Speicher nicht verfügbar – Spiel läuft trotzdem weiter */
  }
}

export function ladeSpiel(): Spielstand | null {
  const s = lesen<Spielstand>(KEY_SPIEL);
  return s && s.version === 1 && Array.isArray(s.spieler) ? s : null;
}

export function speichereSpiel(s: Spielstand | null): void {
  schreiben(KEY_SPIEL, s);
}

/** Zuletzt gestellte Frage-IDs, älteste zuerst */
export function ladeHistory(): string[] {
  const h = lesen<string[]>(KEY_HISTORY);
  return Array.isArray(h) ? h : [];
}

export function merkeFrage(id: string): string[] {
  const h = ladeHistory().filter((x) => x !== id);
  h.push(id);
  const neu = h.slice(-HISTORY_MAX);
  schreiben(KEY_HISTORY, neu);
  return neu;
}

export interface LetzteSpieler extends Partial<Einstellungen> {
  namen: string[];
  farben: string[];
  /** Schwierigkeit pro Spieler (fehlt in älteren Speicherständen) */
  schwierigkeiten?: Schwierigkeit[];
  /** Abweichende Schwierigkeit pro Kategorie, pro Spieler */
  proKategorie?: (ProKategorie | undefined)[];
  runden: number;
  /** Alle Kategorien, die es beim Speichern gab (um neue später automatisch zu wählen) */
  bekannteKategorien?: KategorieId[];
}

export function ladeLetzteSpieler(): LetzteSpieler | null {
  return lesen<LetzteSpieler>(KEY_LETZTE_SPIELER);
}

export function speichereLetzteSpieler(l: LetzteSpieler): void {
  schreiben(KEY_LETZTE_SPIELER, l);
}
