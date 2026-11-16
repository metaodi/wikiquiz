# WikiQuiz – Architektur

Bestätigte Fassung von Schritt 1 (siehe `SPEC.md`).

## Überblick

```
 Wikidata SPARQL ─┐                                   ┌─ generator/out/rejected.jsonl
 Pageviews API ───┤   Python-Generator (offline)      ├─ generator/out/review/*.md
 MediaWiki API ───┼─► Kandidaten → Bekanntheitsfilter ┤
 LLM-API (Key) ───┘   → Templates / LLM + Prüfer      └─ data/fragen/<kategorie>.json (committet)
                      → Validierung → Dedupe                    │
                                                                ▼
                                          PWA (Vite + TS + Svelte 5), GitHub Pages
```

- **Generator** (`generator/`): Python ≥ 3.11, `requests`, später `anthropic`.
  Jede HTTP-Antwort wird in einem SQLite-Cache (`generator/cache/`) abgelegt.
  Rate-Limit pro Host, Retry mit Backoff bei 429/5xx.
  User-Agent: `WikiQuiz-Generator/0.1 (https://github.com/metaodi/wikiquiz; odi@metaodi.ch)`.
- **App** (`app/`): Svelte 5 + Vite + TypeScript + `vite-plugin-pwa`. `questions.json` wird
  vom Service Worker vorab gecacht. Hosting auf GitHub Pages.

## Ordnerstruktur

```
generator/
  wikiquiz_gen/
    cli.py           generate | review | stats
    config.py        Kategorien, Schwellen pro Kategorie, Pfade, Env-Variablen
    http.py          User-Agent, Rate-Limiter, Retry, SQLite-Cache
    sparql.py        Wikidata-SPARQL-Client
    popularity.py    Bekanntheitsfilter (Sitelinks, Pageviews, Ausschlüsse)
    models.py        Frage-Datenklasse, stabile IDs
    validate.py      formale Regeln
    dedupe.py        max. 2 pro Quelle, ähnliche Fragen
    output.py        data/fragen/<kategorie>.json, rejected.jsonl
    review.py        Markdown-Stichproben
    templates/       Wikidata-Templates pro Kategorie
    llm/             (Schritt 3) Prompts, Generierung, Prüfung
  tests/
  cache/  out/       gitignored
app/                 (Schritt 4)
```

## `questions.json`

```json
{
  "version": 1,
  "generiert_am": "2026-11-15T12:00:00Z",
  "fragen": [{
    "id": "wd-3f9a1c2e4b",
    "kategorie": "geografie",
    "frage": "Wie heisst die Hauptstadt von Kanada?",
    "antworten": ["Toronto", "Ottawa", "Montreal", "Vancouver"],
    "korrekt_index": 1,
    "schwierigkeit": 1,
    "quelle_typ": "wikidata",
    "quelle_url": "https://de.wikipedia.org/wiki/Kanada",
    "lizenz": "CC0",
    "quelle_titel": "Kanada",
    "quelle_id": "Q16"
  }]
}
```

- `id`: Präfix (`wd-`/`wp-`) + SHA-1 aus `quelle_id` und Fragetext → stabil über Läufe.
- Kategorie-Slugs: `naturwissenschaften`, `kunst`, `geschichte`, `sport`, `geografie`, `essen`, `natur`,
  `schweiz`, `starwars`, `harrypotter`. Der Slug `geschichte` heisst in der App „Geschichte & Gesellschaft“.
- `quelle_url` zeigt auf den deutschen Wikipedia-Artikel; nur bei Fragen aus der englischen Wikipedia
  (bisher Star Wars und Harry Potter, Themen ohne bekannten deutschen Artikel) auf `https://en.wikipedia.org/wiki/…`.
  Die App erkennt das an der URL und schreibt „Mehr auf Wikipedia (englisch)“.

## Spielstand (localStorage)

- `wikiquiz:game:v1` – `GameState` (Phase, Spieler, Runde, gestellte IDs, aktueller Zug inkl. `timerStart`).
  Beim Neuladen läuft der Timer gemäss `timerStart` weiter; ist er abgelaufen, gilt die Frage als Timeout.
- `wikiquiz:history:v1` – zuletzt gestellte Frage-IDs (ca. 300) über Spiele hinweg.

## Bekanntheitsfilter

Reihenfolge (günstig → teuer): Sitelinks (aus SPARQL) → Titel „Liste …“ / Ereignis jünger als
1 Jahr → Pageviews (60-Tage-Vorfilter im Block, 12 Monate nur im Graubereich) → Seiteninfo
(Begriffsklärung, fehlend, Länge). Für richtige Antworten gilt eine eigene, tiefere Pageview-Schwelle.
Schwellen pro Kategorie in `config.py`, per CLI übersteuerbar.

## Entscheide

| Thema | Entscheid |
|---|---|
| Neuladen während Frage | Timer läuft gemäss `timerStart` weiter |
| LLM | Anthropic Claude, Modelle und Key über Env (`WIKIQUIZ_GEN_MODEL`, `WIKIQUIZ_CHECK_MODEL`, `ANTHROPIC_API_KEY`) |
| Hosting | GitHub Pages; die Fragen (`data/fragen/`) werden committet |
| Rechtschreibung | Alle Texte werden auf „ss“ normalisiert (kein „ß“) |
| Fragenablage | Eine Datei pro Kategorie (`data/fragen/`), der App-Build fügt sie zu `questions.json` zusammen |
| Themenkategorien | Schweiz, Star Wars und Harry Potter liegen quer zu den Fachkategorien: kein Kategorie-Abgleich, tiefere Bekanntheitsschwellen; ein Artikel darf Fragen in einer Fach- und einer Themenkategorie liefern |
| Allgemeinwissen aufgelöst | Zu unscharf: Essen → „Essen & Genuss“, Tiere/Pflanzen → „Tiere & Natur“, Religion/Bräuche/Feiertage/Philosophie → „Geschichte & Gesellschaft“ (Slug `geschichte` bleibt), Spiele → Sport & Unterhaltung, Sprachen → Geografie. Bestehende Fragen behalten ihre ID |
| Englische Wikipedia | Ergänzende Quelle pro Kategorie (`EN_SCHWELLEN`, bisher Star Wars und Harry Potter), nur für Themen, zu denen kein deutscher Artikel den Bekanntheitsfilter besteht. Das LLM formuliert die Fragen auf Deutsch, die Belegstelle bleibt englisch. Eigene Bekanntheitsschwellen, weil en.wikipedia viel mehr Seitenaufrufe hat |
| Neue Kategorien | Gespeicherte Auswahl „alle“ wird um neue Kategorien ergänzt (`bekannteKategorien`), Schlüsselversion bleibt `v1` |
| Automatisierung | GitHub Action „Fragen generieren“: pro Kategorie ein Pull Request im Modus „ergänzen“ mit Stichprobe |
| Themenvielfalt | Wikipedia-Artikel werden reihum nach Thema verarbeitet (Geschichte: Epoche aus Jahreszahlen der Wikipedia-Kategorien, sonst Startkategorie), statt nur nach Seitenaufrufen |
| Aktuelle Politik | Lebende Personen mit laufendem Amt (Wikidata P39 ohne Enddatum, Beginn ≤ 20 Jahre) werden nicht verarbeitet |
| Gleiche Quelle | Die App stellt Fragen zum selben Artikel (`quelle_url`) im selben Spiel erst, wenn keine anderen mehr übrig sind; so verraten sich Fragen zum selben Thema nicht gegenseitig |
