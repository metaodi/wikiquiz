# WikiQuiz – Fragen-Generator

Erzeugt den Fragenpool in `data/fragen/<kategorie>.json` aus Wikidata (Templates) und aus
Wikipedia-Artikeln mit LLM-Generierung und unabhängiger Prüfung. Der App-Build fügt die Dateien
zu `app/public/questions.json` zusammen (`app/scripts/fragen-zusammenfuehren.mjs`).

## Installation

```bash
cd generator
pip install -e ".[llm,dev]"
```

## Bedienung

```bash
# Wikipedia + LLM: Zielbestand 150 Fragen, höchstens 40 Artikel pro Lauf (Kostenbremse)
python -m wikiquiz_gen generate --kategorie kunst --quelle wikipedia --ziel 150 --max-artikel 40

# Nur die Artikelkandidaten nach Bekanntheitsfilter auflisten (ohne LLM, ohne Kosten)
python -m wikiquiz_gen generate --kategorie kunst --quelle wikipedia --nur-kandidaten

# Trockenlauf: Fragen erzeugen (inkl. LLM-Kosten), aber nichts in data/ schreiben
python -m wikiquiz_gen generate --kategorie kunst --quelle wikipedia --max-artikel 10 --dry-run

# Wikidata-Templates neu erzeugen und die bisherigen Wikidata-Fragen der Kategorie ersetzen
python -m wikiquiz_gen generate --kategorie geografie --quelle wikidata --ziel 200 --modus ersetzen

# Review-Stichprobe (30 Fragen pro Kategorie) → out/review/<kategorie>.md
python -m wikiquiz_gen review --kategorie kunst --n 30

# Übersicht
python -m wikiquiz_gen stats
```

Standard ist `--modus ergaenzen`: Bestehende Fragen bleiben unverändert, nur neue IDs kommen dazu.
`data/verarbeitet/<kategorie>.json` merkt sich die bereits verarbeiteten Artikel, damit spätere Läufe
sie nicht erneut (kostenpflichtig) ans LLM schicken.

Ausgaben in `out/`: `rejected.jsonl` (alle verworfenen Kandidaten und Fragen mit Grund),
`zusammenfassung.md` (Zahlen, Tokens, Kostenschätzung) und `review/<kategorie>-neu.md` (Stichprobe der neuen Fragen).

## GitHub Action „Fragen generieren“

`.github/workflows/fragen.yml`, manuell unter *Actions → Fragen generieren → Run workflow*:
Kategorie (oder „alle“), Quelle, Zielbestand, max. Artikel, Trockenlauf. Pro Kategorie entsteht ein
Pull Request mit Zusammenfassung und Stichprobe; `rejected.jsonl` hängt als Artifact am Lauf.

Einmalig nötig:
- *Settings → Actions → General → Allow GitHub Actions to create and approve pull requests*
- Authentifizierung bei Anthropic, eine der beiden Varianten:
  - **Empfohlen: Workload Identity Federation** (kein dauerhafter Schlüssel). In der Claude Console unter
    *Settings → Workload identity → Connect workload → GitHub Actions* einrichten:
    Subject `repo:metaodi/wikiquiz:ref:refs/heads/main`, Audience `https://api.anthropic.com`,
    Claims `repository_owner=metaodi`, `ref=refs/heads/main`. Danach die IDs als
    **Repository-Variablen** hinterlegen: `ANTHROPIC_FEDERATION_RULE_ID`, `ANTHROPIC_ORGANIZATION_ID`,
    `ANTHROPIC_SERVICE_ACCOUNT_ID`, `ANTHROPIC_WORKSPACE_ID`. Der Workflow holt jede Minute ein frisches
    GitHub-OIDC-Token (gültig ca. 5 Minuten, einmal eintauschbar); das SDK tauscht es selbständig.
  - **Alternative: API-Key** als Secret `ANTHROPIC_API_KEY`. Wird nur verwendet, wenn keine Föderation
    konfiguriert ist.
- optional Variablen `WIKIQUIZ_GEN_MODEL` / `WIKIQUIZ_CHECK_MODEL` (sonst `claude-opus-5-5`)

## LLM-Pipeline (Wikipedia)

1. **Artikelauswahl:** Startkategorien pro Quizkategorie (`wikipedia/quellen.py`) sowie exzellente und
   lesenswerte Artikel, die über ihre Wikipedia-Kategorien per Stichwort zugeordnet werden.
   Danach der Bekanntheitsfilter; die bekanntesten Artikel werden zuerst verarbeitet.
2. **Textauszug:** Einleitung und erste Abschnitte, ca. 4000 Zeichen Klartext; Abschnitte wie
   Literatur, Weblinks oder Rezeption werden übersprungen.
3. **Generierung:** Prompt wörtlich aus `SPEC.md` (`llm/prompts.py`, ein Test prüft die Übereinstimmung),
   strukturierte JSON-Ausgabe erzwungen.
4. **Prüfung:** zweiter, unabhängiger Aufruf mit gemischten Antworten, ohne Hinweis auf die richtige.
5. **Aufnahme** nur, wenn: Bekanntheit des Themas ≥ 3, Belegstelle steht im Text (ß/ss und
   Anführungszeichen normalisiert), Prüfer wählt dieselbe Antwort, eindeutig, Allgemeinwissen ≥ 3,
   formale Regeln eingehalten. Danach Deduplizierung gegen den Bestand.

Kosten (grobe Schätzung mit `claude-opus-5-5`, Denkaufwand `medium`): ca. 0.05–0.10 USD pro Artikel,
also rund 5–15 USD für 150 Fragen einer Kategorie. Der Lauf protokolliert die tatsächlichen Tokens.

## Umgebungsvariablen

| Variable | Zweck |
|---|---|
| `WIKIQUIZ_USER_AGENT` | User-Agent für Wikimedia-APIs (Standard mit Kontaktangabe) |
| `WIKIQUIZ_CACHE_DIR` | HTTP-Cache (Standard `generator/cache/`) |
| `WIKIQUIZ_OUT_DIR` | Protokolle und Reviews (Standard `generator/out/`) |
| `WIKIQUIZ_DATA_DIR` | Fragenablage (Standard `data/fragen/`) |
| `ANTHROPIC_API_KEY` | API-Key für die LLM-Pipeline (nur im Generator, nie in der App) |
| `WIKIQUIZ_GEN_MODEL`, `WIKIQUIZ_CHECK_MODEL` | Modelle für Generierung und Prüfung (Standard `claude-opus-5-5`) |
| `WIKIQUIZ_EFFORT` | Denkaufwand `low`/`medium`/`high` (Standard `medium`) |

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
