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

Schwellen pro Kategorie in `wikiquiz_gen/config.py` (per CLI übersteuerbar):

| Schwelle | Standard | Bemerkung |
|---|---|---|
| `min_sitelinks` | 30 (Sport: 50) | wichtigster Indikator, direkt aus SPARQL |
| `min_pageviews` | 200/Tag | abgefragtes Thema, Ø der letzten 12 vollen Monate auf de.wikipedia |
| `min_pageviews_antwort` | 100/Tag | richtige Antwort (z. B. Hauptstadt) – Städteartikel werden seltener aufgerufen als Länderartikel (Ankara ≈ 170, Nairobi ≈ 150) |
| `min_zeichen` | 3000 | Klartext, geschätzt als 60 % der Wikitext-Länge (`prop=info`, 50 Titel/Request) |

Ausgeschlossen werden ausserdem Listen, Begriffsklärungen und Ereignisse jünger als 1 Jahr.

**Seitenaufrufe zweistufig:** Zuerst die 60-Tage-Werte der PageViewInfo-API (50 Titel pro Request).
Nur Kandidaten im Graubereich (0.5×–2× Schwelle) werden über die Pageviews-REST-API auf 12 Monate
verfeinert (1 Titel pro Request, seriell). `--pageviews-exakt` fragt für alle 12 Monate ab.

Alle HTTP-Antworten werden in `cache/http.sqlite` gecacht (TTL 7–30 Tage); wiederholte Läufe
belasten die APIs nicht erneut. Bei HTTP 429 pausiert der Client den Host für alle Threads;
abgeschnittene Antworten (ungültiges JSON) werden nicht gecacht und neu geladen.

## Geografie-Templates (Wikidata)

| Template | Frage | Distraktoren |
|---|---|---|
| `hauptstadt` | Wie heisst die Hauptstadt von {Land}? | Hauptstädte desselben Kontinents mit ähnlicher Bekanntheit; Länder mit mehreren Hauptstädten ausgeschlossen |
| `kontinent` | Auf welchem Kontinent liegt {Land}? | plausible Nachbarkontinente; transkontinentale und umstrittene Fälle ausgeschlossen; max. 25, weniger bekannte Länder zuerst |
| `stadt` / `berg` / `see` | In welchem Land liegt …? | Nachbarländer, sonst bekannte Länder desselben Kontinents; nur Orte mit genau einem Staat (P17), ohne Sondergebiete (Überseegebiete, SAR) |

Schwierigkeit: Rang nach Seitenaufrufen innerhalb des Templates (bekanntestes Drittel = 1).
Länder mit Artikel werden grammatisch korrekt eingesetzt („Hauptstadt der Schweiz“,
„Auf welchem Kontinent liegen die Bahamas?“).
