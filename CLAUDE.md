# CLAUDE.md

Hinweise für Claude Code in diesem Repository. Überblick und Setup: `README.md`; Details in
`app/README.md`, `generator/README.md`, `docs/ARCHITEKTUR.md`. Der ursprüngliche Auftrag steht in `SPEC.md`.

## Projekt

WikiQuiz = Pass-and-Play-Quiz-PWA (1–4 Spieler, ein Gerät) mit Fragen aus de.wikipedia und Wikidata.
Zwei getrennte Teile, verbunden nur über die JSON-Dateien in `data/fragen/`:

- `generator/` – Python ≥ 3.11, Paket `wikiquiz_gen`. Erzeugt Fragen offline (Wikidata-Templates und
  Wikipedia + Claude mit unabhängiger Prüfung) und schreibt `data/fragen/<kategorie>.json`.
- `app/` – Svelte 5 + Vite + TypeScript + `vite-plugin-pwa`, kein Backend. `scripts/fragen-zusammenfuehren.mjs`
  baut vor `dev`/`build` daraus `public/questions.json` (gitignored, nie von Hand bearbeiten).

## Befehle

```bash
# Generator
cd generator && pip install -e ".[llm,dev]"
python -m pytest -q                       # schnell, ohne Netzwerk
python -m wikiquiz_gen stats

# App
cd app && npm install
npm run check && npm test                 # svelte-check + Vitest
npm run e2e                               # Playwright (Chromium, Pixel-7-Viewport), --trace off ist gesetzt
npm run build
```

Vor einem Commit die Tests des betroffenen Teils laufen lassen; bei UI-Änderungen auch `npm run e2e`.
In der Cloud-Umgebung ist Chromium vorinstalliert – `playwright install` nicht ausführen.

## Konventionen

- **Sprache:** Code-Bezeichner, Kommentare, UI-Texte, Commit-Messages und Doku auf **Deutsch** mit Schweizer
  Rechtschreibung: immer „ss“, **nie „ß“** (ein E2E-Test und der Generator prüfen das). Umlaute in Bezeichnern
  werden umschrieben (`ergaenzen`, `Uebergabe.svelte`).
- **Commit-Messages:** kurzer deutscher Satz im Infinitiv/Imperativ-Stil, z. B. „Sitelinks über SPARQL statt wbgetentities“.
- **Spiellogik** (`app/src/lib/game.ts`) bleibt aus reinen Funktionen; Zeit und Zufall werden hereingereicht.
  Zeitlimit, Punkteformel, Runden und Farben gehören in `app/src/lib/config.ts`.
- **`localStorage`**-Zugriffe nur über `app/src/lib/storage.ts` (alles in try/catch). Schlüssel sind versioniert
  (`wikiquiz:game:v1`, `wikiquiz:history:v1`); bei inkompatiblen Änderungen Version erhöhen.
- **UX:** mobile-first, Touch-Targets ≥ 48 px, kein horizontales Scrollen bei 320 px (E2E-Tests prüfen das).
- **E2E-Tests** liefern Fixture-Fragen per `page.route` und steuern die Zeit mit Playwrights Fake-Clock.
  Neue Spielfunktionen bekommen einen E2E-Test in `app/e2e/`.

## Generator – wichtige Regeln

- **Prompts:** `generator/wikiquiz_gen/llm/prompts.py` muss wörtlich mit den Prompts in `SPEC.md` übereinstimmen
  (`tests/test_prompts.py` prüft das). Prompt ändern = beide Stellen ändern.
- **Frage-IDs** sind stabil (Präfix `wd-`/`wp-` + SHA-1 aus `quelle_id` und Fragetext, `models.py`).
  Format von `questions.json` nicht brechen; Beschreibung in `docs/ARCHITEKTUR.md`.
- Standardmodus `--modus ergaenzen`: bestehende Fragen bleiben unverändert. `data/verarbeitet/` merkt sich
  bereits verarbeitete Artikel – nicht löschen, sonst entstehen erneut LLM-Kosten.
- **Keine LLM-Läufe ohne Auftrag:** `--quelle wikipedia` kostet Geld (ca. 0.05–0.10 USD pro Artikel).
  Zum Ausprobieren `--nur-kandidaten` (ohne LLM) oder kleine `--max-artikel` mit `--dry-run` verwenden.
- Wikimedia-APIs schonen: alles läuft über `wikiquiz_gen/http.py` (User-Agent, Rate-Limit, Retry, SQLite-Cache in
  `generator/cache/`). Keine direkten `requests`-Aufrufe an anderen Stellen.
- Modelle über `WIKIQUIZ_GEN_MODEL` / `WIKIQUIZ_CHECK_MODEL` (Standard `claude-opus-5-5`), Aufwand über `WIKIQUIZ_EFFORT`.
  Ein API-Key gehört nie in die App oder ins Repository.
- Schwellen des Bekanntheitsfilters pro Kategorie in `wikiquiz_gen/config.py`; neue Wikidata-Templates unter
  `wikiquiz_gen/templates/` und im Generator-README dokumentieren.

## Daten und Deployment

- `data/fragen/*.json` sind committet und werden normalerweise über den Workflow „Fragen generieren“
  (`.github/workflows/fragen.yml`) per Pull Request ergänzt – nicht von Hand massenhaft ändern.
- Push auf `main` deployt die App auf GitHub Pages (`BASE_PATH=/wikiquiz/`).
- Nicht committen: `generator/cache/`, `generator/out/`, `app/public/questions.json`, `node_modules/`, `dist/`.

## Doku pflegen

Verhaltensänderungen in der App → `app/README.md`; Generator-Optionen, Variablen, Schwellen → `generator/README.md`;
Architektur-Entscheide → Tabelle „Entscheide“ in `docs/ARCHITEKTUR.md`.
