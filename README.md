# WikiQuiz

Mobile Quiz-App für 1–4 Spieler im Pass-and-Play-Modus: Alle spielen abwechselnd auf einem Gerät,
das jeweils weitergegeben wird. Die Fragen stammen aus der deutschsprachigen Wikipedia und aus Wikidata.

**Spielen:** <https://metaodi.ch/wikiquiz> (installierbar als App, funktioniert offline)

## Wie es funktioniert

Das Projekt besteht aus zwei getrennten Teilen:

```
 Wikidata (SPARQL) ─┐                                       
 Pageviews-API ─────┤   generator/  (Python, offline)        data/fragen/<kategorie>.json
 MediaWiki-API ─────┼─► Bekanntheitsfilter → Templates  ───►  (committet, per Pull Request)
 Anthropic-API ─────┘   bzw. LLM + unabhängige Prüfung                 │
                                                                       ▼
                                          app/  (Svelte-PWA, ohne Backend) → GitHub Pages
```

1. **Fragen-Generator** ([`generator/`](generator/README.md)) erzeugt vorab einen geprüften Fragenpool –
   aus Wikidata-Templates (ohne LLM) und aus Wikipedia-Artikeln mit Claude (Generierung + unabhängige Prüfung).
   Ein Bekanntheitsfilter (Sprachversionen, Seitenaufrufe, Artikellänge) sorgt dafür, dass kein Nischenwissen abgefragt wird.
   Der API-Key liegt ausschliesslich hier, nie in der App.
2. **App** ([`app/`](app/README.md)) ist eine Progressive Web App (Svelte 5, Vite, TypeScript). Beim Build werden die
   Dateien aus `data/fragen/` zu `questions.json` zusammengeführt und vom Service Worker gecacht.
   Spielstand und Verlauf liegen in `localStorage`.

Die Fragen werden also nicht live während des Spiels erzeugt: keine Wartezeit, keine Kosten pro Spiel,
und jede neue Fragenserie wird in einem Pull Request geprüft, bevor sie live geht.

### Spielablauf in Kürze

- Setup: 1–4 Spieler mit Namen und Farbe, 5/10/15 Runden, Kategorie-Wahl-Modus und Kategorienauswahl
- Kategorien: Naturwissenschaften & Technik, Kunst/Musik/Literatur, Geschichte & Gesellschaft, Sport & Unterhaltung,
  Geografie, Essen & Genuss, Tiere & Natur sowie die Themenkategorien Schweiz und Star Wars – oder „Zufall“
- Pro Frage 4 Antworten und 15 Sekunden; Punkte `round(100 − 90 × t/15)` für richtige Antworten
- Feedback mit Link zum Wikipedia-Artikel, Zwischenstand nach jeder Runde, Rangliste am Ende

## Projektstruktur

| Pfad | Inhalt |
|---|---|
| [`SPEC.md`](SPEC.md) | Ursprünglicher Auftrag inkl. der verbindlichen LLM-Prompts |
| [`docs/ARCHITEKTUR.md`](docs/ARCHITEKTUR.md) | Architektur, Datenformat `questions.json`, Entscheide |
| [`app/`](app/README.md) | PWA: Spiellogik, Screens, Unit- und End-to-End-Tests |
| [`generator/`](generator/README.md) | Python-Paket `wikiquiz_gen`: Wikidata-Templates, Wikipedia + LLM, Filter, Review |
| `data/fragen/` | Fragenpool, eine JSON-Datei pro Kategorie (Quelle der Wahrheit für die App) |
| `data/verarbeitet/` | Bereits ans LLM geschickte Artikel pro Kategorie (verhindert doppelte Kosten) |
| `.github/workflows/` | CI, Deployment auf GitHub Pages, Fragengenerierung |

## Setup

Voraussetzungen: **Node.js 22** und **Python ≥ 3.11**.

### App

```bash
cd app
npm install
npm run dev        # Entwicklungsserver (führt vorher die Fragen zu public/questions.json zusammen)
npm run check      # Typprüfung
npm test           # Unit-Tests (Vitest)
npm run e2e        # End-to-End-Tests (Playwright; einmalig: npx playwright install chromium)
npm run build      # Produktions-Build nach dist/
```

### Generator

```bash
cd generator
pip install -e ".[llm,dev]"     # am besten in einer virtuellen Umgebung
python -m pytest -q             # Tests (ohne Netzwerk)
python -m wikiquiz_gen stats    # Anzahl Fragen pro Kategorie

# Wikidata-Fragen (ohne LLM, ohne Kosten)
python -m wikiquiz_gen generate --kategorie geografie --quelle wikidata --ziel 200

# Wikipedia + LLM (braucht ANTHROPIC_API_KEY; --dry-run schreibt nichts nach data/)
export ANTHROPIC_API_KEY=…
python -m wikiquiz_gen generate --kategorie kunst --quelle wikipedia --ziel 150 --max-artikel 40
```

Alle Optionen, Umgebungsvariablen, Schwellen des Bekanntheitsfilters und eine Kostenschätzung stehen im
[Generator-README](generator/README.md).

## GitHub Actions

| Workflow | Auslöser | Zweck |
|---|---|---|
| `ci.yml` – *Tests* | jeder Push und PR | Generator: pytest · App: Typprüfung, Vitest, Playwright |
| `pages.yml` | Push auf `main` | App bauen und auf GitHub Pages veröffentlichen |
| `fragen.yml` – *Fragen generieren* | manuell | Fragen pro Kategorie erzeugen, je Kategorie ein Pull Request mit Stichprobe |

Einmalige Einrichtung im Repository:

- *Settings → Pages → Source: GitHub Actions*
- *Settings → Actions → General → Allow GitHub Actions to create and approve pull requests*
- Anthropic-Anmeldung für „Fragen generieren“: bevorzugt **Workload Identity Federation** (Repository-Variablen
  `ANTHROPIC_FEDERATION_RULE_ID`, `ANTHROPIC_ORGANIZATION_ID`, `ANTHROPIC_SERVICE_ACCOUNT_ID`, `ANTHROPIC_WORKSPACE_ID`),
  alternativ Secret `ANTHROPIC_API_KEY`. Details im [Generator-README](generator/README.md#github-action-fragen-generieren).

## Lizenzen der Inhalte

Fragen aus Wikidata stehen unter CC0, Fragen auf Basis von Wikipedia-Artikeln unter CC BY-SA 4.0.
Jede Frage verweist auf ihren Quellartikel; die Info-Seite der App enthält die Quellen- und Lizenzhinweise.
