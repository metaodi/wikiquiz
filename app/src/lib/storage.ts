/** localStorage- und sessionStorage-Zugriffe, alle in try/catch (privater Modus, gesperrter Speicher …). */
import { HISTORY_MAX } from './config';
import type { Teilnehmer } from './raum';
import type { Einstellungen, KategorieId, ProKategorie, Schwierigkeit, Spielstand, StufenWahl } from './types';

const KEY_SPIEL = 'wikiquiz:game:v1';
const KEY_HISTORY = 'wikiquiz:history:v1';
const KEY_LETZTE_SPIELER = 'wikiquiz:players:v1';
// Pro Tab (sessionStorage): mehrere Tabs im selben Browser sind verschiedene Geräte
const KEY_RAUM = 'wikiquiz:raum:v1';
const KEY_GERAET = 'wikiquiz:geraet:v1';

type Speicher = 'local' | 'session';

function speicher(art: Speicher): Storage {
  return art === 'local' ? localStorage : sessionStorage;
}

function lesen<T>(key: string, art: Speicher = 'local'): T | null {
  try {
    const roh = speicher(art).getItem(key);
    return roh ? (JSON.parse(roh) as T) : null;
  } catch {
    return null;
  }
}

function schreiben(key: string, wert: unknown, art: Speicher = 'local'): void {
  try {
    if (wert === null) speicher(art).removeItem(key);
    else speicher(art).setItem(key, JSON.stringify(wert));
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
  /** Gemeinsame Stufe im Raum beim Ablauf „Alle gleichzeitig“ */
  raumSchwierigkeit?: Schwierigkeit;
  /** Eigene Schwierigkeitswahl beim Spielen mit mehreren Geräten */
  raumWahl?: StufenWahl;
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

/** Übertragungsweg eines Raums: WebRTC (`netz`) oder Tabs im selben Browser (`tabs`, Tests und Entwicklung) */
export type KanalArt = 'netz' | 'tabs';

/** Raum, in dem dieser Tab mitspielt – übersteht ein Neuladen. Der Host merkt sich auch Teilnehmer und Spiel. */
export interface RaumSitzung {
  code: string;
  rolle: 'host' | 'gast';
  /** Fehlt bei Sitzungen aus der Vorschau-Zeit → `netz` */
  kanal?: KanalArt;
  name: string;
  /** Eigene Schwierigkeitswahl (Gast: wird nach dem Neuladen erneut mit `hallo` geschickt) */
  wahl?: StufenWahl;
  teilnehmer?: Teilnehmer[];
  spiel?: Spielstand | null;
}

export function ladeRaum(): RaumSitzung | null {
  const r = lesen<RaumSitzung>(KEY_RAUM, 'session');
  return r && typeof r.code === 'string' && (r.rolle === 'host' || r.rolle === 'gast') ? r : null;
}

export function speichereRaum(r: RaumSitzung | null): void {
  schreiben(KEY_RAUM, r, 'session');
}

/** Zufällige, pro Tab feste Geräte-ID (damit ein Gast nach dem Neuladen wiedererkannt wird) */
export function geraetId(neu: () => string): string {
  const id = lesen<string>(KEY_GERAET, 'session');
  if (typeof id === 'string' && id) return id;
  const erzeugt = neu();
  schreiben(KEY_GERAET, erzeugt, 'session');
  return erzeugt;
}
