import { describe, expect, it } from 'vitest';
import { quellenLinkText, wikiSprache } from '../src/lib/quelle';

describe('Quellenlink', () => {
  it('erkennt die Sprache der Wikipedia', () => {
    expect(wikiSprache('https://de.wikipedia.org/wiki/K%C3%B6ln')).toBe('de');
    expect(wikiSprache('https://en.wikipedia.org/wiki/Darth_Vader')).toBe('en');
    expect(wikiSprache('https://www.wikidata.org/wiki/Q1')).toBeNull();
  });

  it('kennzeichnet englische Artikel', () => {
    expect(quellenLinkText({ quelle_url: 'https://de.wikipedia.org/wiki/Bern', quelle_titel: 'Bern' })).toBe(
      'Mehr auf Wikipedia: Bern',
    );
    expect(
      quellenLinkText({ quelle_url: 'https://en.wikipedia.org/wiki/Darth_Vader', quelle_titel: 'Darth Vader' }),
    ).toBe('Mehr auf Wikipedia (englisch): Darth Vader');
    expect(quellenLinkText({ quelle_url: 'https://en.wikipedia.org/wiki/Jedi' })).toBe(
      'Mehr auf Wikipedia (englisch)',
    );
  });
});
