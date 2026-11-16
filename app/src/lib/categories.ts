import type { KategorieId } from './types';

export interface Kategorie {
  id: KategorieId;
  name: string;
  farbe: string;
  /** Textfarbe auf `farbe` */
  text: string;
  icon: string;
}

export const KATEGORIEN: Kategorie[] = [
  { id: 'naturwissenschaften', name: 'Naturwissenschaften & Technik', farbe: '#1565c0', text: '#fff', icon: '🔬' },
  { id: 'kunst', name: 'Kunst, Musik & Literatur', farbe: '#8e24aa', text: '#fff', icon: '🎨' },
  { id: 'geschichte', name: 'Geschichte & Gesellschaft', farbe: '#8d5524', text: '#fff', icon: '🏛️' },
  { id: 'sport', name: 'Sport & Unterhaltung', farbe: '#e65100', text: '#fff', icon: '⚽' },
  { id: 'geografie', name: 'Geografie', farbe: '#2e7d32', text: '#fff', icon: '🌍' },
  { id: 'essen', name: 'Essen & Genuss', farbe: '#f9a825', text: '#1f2a44', icon: '🍽️' },
  { id: 'natur', name: 'Tiere & Natur', farbe: '#00796b', text: '#fff', icon: '🐾' },
  { id: 'schweiz', name: 'Schweiz', farbe: '#d52b1e', text: '#fff', icon: '🇨🇭' },
  { id: 'starwars', name: 'Star Wars', farbe: '#1b1b1b', text: '#ffe81f', icon: '🌌' },
  { id: 'harrypotter', name: 'Harry Potter', farbe: '#7b1e2b', text: '#f6d36b', icon: '⚡' },
];

/**
 * Kategorien der ersten Version (für Speicherstände ohne `bekannteKategorien`). Wer damals alle gewählt
 * hatte, bekommt neue dazu. „allgemeinwissen“ gibt es nicht mehr (aufgeteilt auf Geschichte & Gesellschaft,
 * Essen & Genuss, Tiere & Natur, Sport, Geografie), steht hier aber für alte Speicherstände.
 */
export const URSPRUENGLICHE_KATEGORIEN: string[] = [
  'naturwissenschaften', 'kunst', 'geschichte', 'sport', 'geografie', 'allgemeinwissen',
];

export const KATEGORIE_MAP: Record<KategorieId, Kategorie> = Object.fromEntries(
  KATEGORIEN.map((k) => [k.id, k]),
) as Record<KategorieId, Kategorie>;
