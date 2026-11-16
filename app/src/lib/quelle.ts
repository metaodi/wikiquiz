import type { Frage } from './types';

/** Sprachkürzel der Wikipedia, aus der eine Frage stammt („de“, „en“ …); null bei anderen Quellen. */
export function wikiSprache(url: string): string | null {
  const m = /^https:\/\/([a-z-]+)\.wikipedia\.org\//.exec(url);
  return m ? m[1] : null;
}

/** Linktext unter dem Feedback, z. B. „Mehr auf Wikipedia (englisch): Darth Vader“. */
export function quellenLinkText(frage: Pick<Frage, 'quelle_url' | 'quelle_titel'>): string {
  const sprache = wikiSprache(frage.quelle_url);
  const zusatz = sprache === 'en' ? ' (englisch)' : '';
  return `Mehr auf Wikipedia${zusatz}${frage.quelle_titel ? `: ${frage.quelle_titel}` : ''}`;
}
