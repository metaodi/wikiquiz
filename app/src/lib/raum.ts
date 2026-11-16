/**
 * Spielen mit mehreren Geräten: Ein Gerät eröffnet einen Raum und leitet das Spiel (Host),
 * jedes Gerät steuert genau einen Spieler. Reine Funktionen, siehe docs/ARCHITEKTUR.md.
 */
import type { Aktion } from './aktionen';
import { MAX_SPIELER, SPIELER_FARBEN } from './config';
import { proKategoriePruefen, waehler } from './game';
import { stufe, type Rng } from './picker';
import type { Spielstand, StufenWahl } from './types';

export interface Teilnehmer extends Partial<StufenWahl> {
  /** Zufällige ID des Geräts (pro Browser-Tab) */
  geraet: string;
  name: string;
  farbe: string;
}

/** Schwierigkeitswahl aus einer Nachricht bereinigen (fehlt bei älteren Versionen → Standard) */
export function stufenWahlPruefen(w: { schwierigkeit?: unknown; proKategorie?: unknown } | undefined): StufenWahl {
  const schwierigkeit = stufe(w?.schwierigkeit);
  const proKategorie = proKategoriePruefen(w?.proKategorie, schwierigkeit);
  return proKategorie ? { schwierigkeit, proKategorie } : { schwierigkeit };
}

/** Kein Spieler, sondern der Host bedient die aktuelle Phase */
export const HOST = -1;
/** Alle Spieler zugleich („Alle gleichzeitig“: jeder beantwortet die Frage auf seinem Gerät) */
export const ALLE = -2;

/** Index des Spielers, dessen Gerät die aktuelle Phase bedient – oder `HOST` bzw. `ALLE`. */
export function zustaendig(s: Spielstand): number {
  const gleichzeitig = s.ablauf === 'gleichzeitig';
  switch (s.phase) {
    case 'frage':
      return gleichzeitig ? ALLE : s.aktiverSpieler;
    case 'uebergabe':
    case 'zufall':
      return s.aktiverSpieler;
    case 'kategorie':
      return waehler(s);
    case 'feedback':
      // Gleichzeitig: alle sehen ihr Ergebnis, weiter geht es beim Host
      return gleichzeitig ? HOST : (s.zug?.spieler ?? s.aktiverSpieler);
    default:
      return HOST;
  }
}

/** Darf das Gerät `von` diese Aktion jetzt auslösen? Der Host prüft das für jede empfangene Aktion. */
export function darf(s: Spielstand, teilnehmer: Teilnehmer[], hostGeraet: string, von: string, aktion: Aktion): boolean {
  // Zeitablauf melden darf jedes Gerät; der Host prüft die Zeit ohnehin selbst
  if (aktion.typ === 'zeitPruefen') return true;
  // Der Host darf das Spiel jederzeit beenden (z. B. wenn ein Gerät nicht mehr reagiert)
  if (aktion.typ === 'beenden' && von === hostGeraet) return true;
  const z = zustaendig(s);
  if (z === ALLE) return teilnehmer.some((t) => t.geraet === von);
  return z === HOST ? von === hostGeraet : teilnehmer[z]?.geraet === von;
}

export type BeitrittsFehler = 'laeuft' | 'voll' | 'name' | 'fragen';

export const BEITRITTS_FEHLER: Record<BeitrittsFehler, string> = {
  laeuft: 'In diesem Raum läuft bereits ein Spiel.',
  voll: `Der Raum ist voll (höchstens ${MAX_SPIELER} Spieler).`,
  name: 'Dieser Name ist im Raum schon vergeben.',
  fragen: 'Dieses Gerät und der Host haben nicht dieselben Fragen. Bitte auf beiden Geräten die App neu laden.',
};

/**
 * Gerät tritt dem Raum bei. Voraussetzung ist derselbe Fragenstand wie beim Host (`gleicheFragen`).
 * Bekannte Geräte (z. B. nach Neuladen) sind dann immer willkommen; neue nur, solange kein Spiel läuft,
 * Platz frei ist und der Name noch nicht vergeben ist. Die Farbe vergibt der Host: die erste noch freie.
 * Die Schwierigkeit wählt das Gerät selbst (`wahl`), der Host prüft sie.
 */
export function beitreten(
  teilnehmer: Teilnehmer[],
  geraet: string,
  name: string,
  spielLaeuft: boolean,
  gleicheFragen = true,
  wahl?: { schwierigkeit?: unknown; proKategorie?: unknown },
): { ok: true; teilnehmer: Teilnehmer[] } | { ok: false; fehler: BeitrittsFehler } {
  if (!gleicheFragen) return { ok: false, fehler: 'fragen' };
  if (teilnehmer.some((t) => t.geraet === geraet)) return { ok: true, teilnehmer };
  if (spielLaeuft) return { ok: false, fehler: 'laeuft' };
  if (teilnehmer.length >= MAX_SPIELER) return { ok: false, fehler: 'voll' };
  const n = name.trim();
  if (teilnehmer.some((t) => t.name.toLowerCase() === n.toLowerCase())) return { ok: false, fehler: 'name' };
  const farbe = SPIELER_FARBEN.find((f) => !teilnehmer.some((t) => t.farbe === f)) ?? SPIELER_FARBEN[0];
  return { ok: true, teilnehmer: [...teilnehmer, { geraet, name: n, farbe, ...stufenWahlPruefen(wahl) }] };
}

export function verlassen(teilnehmer: Teilnehmer[], geraet: string): Teilnehmer[] {
  return teilnehmer.filter((t) => t.geraet !== geraet);
}

/** Ohne leicht verwechselbare Zeichen (I, O, 0, 1) */
const CODE_ZEICHEN = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
export const CODE_LAENGE = 4;

export function zufallsCode(rng: Rng, laenge = CODE_LAENGE): string {
  let code = '';
  for (let i = 0; i < laenge; i++) code += CODE_ZEICHEN[Math.floor(rng() * CODE_ZEICHEN.length)];
  return code;
}

/** Eingabe vereinheitlichen: Grossbuchstaben, ohne Leer- und Sonderzeichen */
export function codeNormalisieren(eingabe: string): string {
  return eingabe.toUpperCase().replace(/[^A-Z0-9]/g, '');
}
