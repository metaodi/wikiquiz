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
  { id: 'geschichte', name: 'Geschichte', farbe: '#8d5524', text: '#fff', icon: '🏛️' },
  { id: 'sport', name: 'Sport & Unterhaltung', farbe: '#e65100', text: '#fff', icon: '⚽' },
  { id: 'geografie', name: 'Geografie', farbe: '#2e7d32', text: '#fff', icon: '🌍' },
  { id: 'allgemeinwissen', name: 'Allgemeinwissen', farbe: '#f9a825', text: '#1f2a44', icon: '💡' },
];

export const KATEGORIE_MAP: Record<KategorieId, Kategorie> = Object.fromEntries(
  KATEGORIEN.map((k) => [k.id, k]),
) as Record<KategorieId, Kategorie>;
