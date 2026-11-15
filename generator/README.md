# WikiQuiz – Fragen-Generator

Erzeugt `app/public/questions.json` aus Wikidata (Templates) und – ab Schritt 3 – aus
Wikipedia-Artikeln mit LLM-Generierung und unabhängiger Prüfung.

## Installation

```bash
cd generator
pip install -e ".[dev]"        # später für die LLM-Pipeline: ".[llm,dev]"
```

## Bedienung

```bash
# Trockenlauf: nichts schreiben, Stichprobe als Markdown ausgeben
python -m wikiquiz_gen generate --kategorie geografie --dry-run

# Schreiben (ersetzt die Wikidata-Fragen der Kategorie in questions.json)
python -m wikiquiz_gen generate --kategorie geografie --ziel 200

# Nur neue Fragen ergänzen, bestehende IDs bleiben unverändert
python -m wikiquiz_gen generate --kategorie geografie --modus ergaenzen

# Schwellen übersteuern
python -m wikiquiz_gen generate --kategorie geografie --min-sitelinks 50 --min-pageviews 500 --dry-run

# Review-Stichprobe (30 Fragen pro Kategorie) → out/review/<kategorie>.md
python -m wikiquiz_gen review --kategorie geografie --n 30

# Übersicht
python -m wikiquiz_gen stats
```

Verworfene Kandidaten und Fragen landen mit Grund in `out/rejected.jsonl`
(Bekanntheitsfilter, formale Regeln, Deduplizierung), um Schwellen nachzujustieren.

## Umgebungsvariablen

| Variable | Zweck |
|---|---|
| `WIKIQUIZ_USER_AGENT` | User-Agent für Wikimedia-APIs (Standard mit Kontaktangabe) |
| `WIKIQUIZ_CACHE_DIR` | HTTP-Cache (Standard `generator/cache/`) |
| `WIKIQUIZ_OUT_DIR` | Protokolle und Reviews (Standard `generator/out/`) |
| `WIKIQUIZ_QUESTIONS` | Zieldatei (Standard `app/public/questions.json`) |
| `ANTHROPIC_API_KEY`, `WIKIQUIZ_GEN_MODEL`, `WIKIQUIZ_CHECK_MODEL` | LLM (Schritt 3) |

## Bekanntheitsfilter

Schwellen pro Kategorie in `wikiquiz_gen/config.py`: mind. 30 Sitelinks (Sport: 50),
im Schnitt mind. 200 Aufrufe/Tag auf de.wikipedia über die letzten 12 vollen Monate,
mind. 3000 Zeichen Klartext; Listen, Begriffsklärungen und Ereignisse jünger als 1 Jahr
werden ausgeschlossen.

Alle HTTP-Antworten werden in `cache/http.sqlite` gecacht (TTL 7–30 Tage); wiederholte Läufe
belasten die APIs nicht erneut. Die Pageviews-API wird seriell abgefragt (sie drosselt
parallele Anfragen), bei HTTP 429 pausiert der Client den Host für alle Threads.

## Geografie-Templates (Wikidata)

| Template | Frage | Distraktoren |
|---|---|---|
| `hauptstadt` | Wie heisst die Hauptstadt von {Land}? | Hauptstädte desselben Kontinents mit ähnlicher Bekanntheit; Länder mit mehreren Hauptstädten ausgeschlossen |
| `kontinent` | Auf welchem Kontinent liegt {Land}? | plausible Nachbarkontinente; transkontinentale Staaten ausgeschlossen |
| `stadt` / `berg` / `see` | In welchem Land liegt …? | Nachbarländer, sonst Länder desselben Kontinents; nur Orte mit genau einem Staat (P17) |
