export type KategorieId =
  | 'naturwissenschaften'
  | 'kunst'
  | 'geschichte'
  | 'sport'
  | 'geografie'
  | 'allgemeinwissen';

export interface Frage {
  id: string;
  kategorie: KategorieId;
  frage: string;
  antworten: string[];
  korrekt_index: number;
  schwierigkeit: 1 | 2 | 3;
  quelle_typ: 'wikidata' | 'wikipedia';
  quelle_url: string;
  lizenz: string;
  quelle_titel?: string;
  quelle_id?: string;
}

export interface Pool {
  version: number;
  generiert_am: string | null;
  fragen: Frage[];
}

export interface Spieler {
  name: string;
  farbe: string;
  punkte: number;
}

export interface Zug {
  spieler: number;
  kategorie: KategorieId;
  zufall: boolean;
  frageId: string;
  /** Anzeige-Reihenfolge: Indizes in frage.antworten */
  reihenfolge: number[];
  /** Zeitpunkt (ms, Date.now), ab dem Frage und Antworten vollständig sichtbar sind */
  timerStart: number | null;
  /** Index in frage.antworten, null = Zeit abgelaufen */
  gewaehlt: number | null;
  /** Antwortzeit in Sekunden ab timerStart */
  zeit: number | null;
  punkte: number;
  richtig: boolean;
}

export type Phase =
  | 'setup'
  | 'uebergabe'
  | 'kategorie'
  | 'zufall'
  | 'frage'
  | 'feedback'
  | 'zwischenstand'
  | 'rangliste';

export interface Spielstand {
  version: 1;
  phase: Phase;
  spieler: Spieler[];
  runden: number;
  /** 1-basiert */
  runde: number;
  aktiverSpieler: number;
  /** In diesem Spiel bereits gestellte Frage-IDs */
  gestellt: string[];
  zug: Zug | null;
}
