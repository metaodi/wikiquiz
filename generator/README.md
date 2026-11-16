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

# Fragen per ID in eine andere Kategorie verschieben (IDs bleiben gleich)
python -m wikiquiz_gen verschieben --nach geschichte --id wp-0cc912c042 --id wp-4c43317216

# Fragen per ID löschen (der Artikel bleibt in data/verarbeitet/ vermerkt und wird nicht erneut verarbeitet)
python -m wikiquiz_gen entfernen --id wp-0e431a70e4 --id wp-4690569104

# Anführungszeichen («…») und Schweizer Rechtschreibung in bestehenden Fragen vereinheitlichen
python -m wikiquiz_gen bereinigen --dry-run
```

Standard ist `--modus ergaenzen`: Bestehende Fragen bleiben unverändert, nur neue IDs kommen dazu.
`--modus ersetzen` erzeugt die **Wikidata-Fragen** einer Kategorie neu (z. B. nach einer Template-Änderung);
Wikipedia-Fragen werden auch dann nur ergänzt, weil die Pipeline nur den fehlenden Bedarf erzeugt und ein
Ersetzen bereits bezahlte Fragen löschen würde.
`data/verarbeitet/<kategorie>.json` merkt sich die bereits verarbeiteten Artikel, damit spätere Läufe
sie nicht erneut (kostenpflichtig) ans LLM schicken.

Ausgaben in `out/`: `rejected.jsonl` (alle verworfenen Kandidaten und Fragen mit Grund),
`zusammenfassung.md` (Zahlen, Tokens, Kostenschätzung) und `review/<kategorie>-neu.md` (Stichprobe der neuen Fragen).

## GitHub Action „Fragen generieren“

`.github/workflows/fragen.yml`, manuell unter *Actions → Fragen generieren → Run workflow*:
Kategorie (oder „alle“), Quelle, Zielbestand, max. Artikel, Modus (`ergaenzen`/`ersetzen`, siehe oben), Trockenlauf.
Wikidata-Läufe brauchen kein LLM und kosten nichts. Pro Kategorie entsteht ein
Pull Request mit Prüfliste, Zusammenfassung und Stichprobe; `rejected.jsonl` hängt als Artifact am Lauf.

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
   **Kategorie-Abgleich:** Zeigen die Wikipedia-Kategorien und die Wikidata-Berufe (P106) eines Artikels
   eindeutig auf eine andere Quizkategorie, wird er übersprungen (z. B. Friedrich II. aus „Komponist (Klassik)“
   → Geschichte, Johannes Kepler → Naturwissenschaften). Stichworte zählen nur am Wortanfang („Verdichter“ ist
   kein „Dichter“); „Literatur (…)“ zählt nicht, weil Wikipedia so alle einordnet, die etwas veröffentlicht haben.
   Stichworte und Berufe stehen in `wikipedia/quellen.py`. Flugzeugtypen (Kategorien „Erstflug …“,
   „… Flugzeug“) zählen zur Technik, auch militärische.
   **Amtierende Personen:** Lebende Personen, die laut Wikidata gerade ein Amt innehaben (Position P39 mit
   Beginn in den letzten 20 Jahren, ohne Enddatum), werden übersprungen (z. B. Friedrich Merz). Fragen zu
   ihnen veralten schnell.
   **Themenvielfalt:** Jeder Artikel bekommt ein Thema: in der Geschichte die Epoche (Antike, Mittelalter,
   Frühe Neuzeit, 1789–1914, 1914–1945, seit 1945; geschätzt aus Jahreszahlen in den Wikipedia-Kategorien
   wie „Geboren 1638“ oder „Herrscher (17. Jahrhundert)“, sonst aus dem Ereignisdatum in Wikidata; NS-Zeit
   und Weltkriege per Stichwort; ohne Jahr ein gemeinsamer Topf „ohne Epoche“), sonst die Startkategorie. Verarbeitet wird reihum zuerst aus dem Thema mit den bisher wenigsten Fragen (Bestand
   eingerechnet), innerhalb eines Themas nach Seitenaufrufen (`wikipedia/themen.py`). So überwiegen nicht
   allein die meistgelesenen Themen (in der Geschichte NS-Zeit und Zweiter Weltkrieg).
   **Themenkategorien** (`schweiz`, `starwars`; `THEMENKATEGORIEN` in `config.py`) liegen quer zu den
   Fachkategorien: Für sie entfällt der Kategorie-Abgleich (ein Bundesrat bleibt in „Schweiz“, obwohl er sonst
   „Geschichte“ wäre). Exzellente und lesenswerte Artikel kommen dazu, wenn eine ihrer Wikipedia-Kategorien ein
   Themen-Stichwort enthält (`THEMEN_STICHWORTE`, z. B. „(Schweiz)“, „in der Schweiz“, „Star Wars“). Dieselben
   Artikel können zusätzlich Fragen in ihrer Fachkategorie liefern. Für Themenkategorien gibt es (noch) keine
   Wikidata-Templates. Leere oder nicht existierende Startkategorien werden im Log gemeldet.
   **Englische Wikipedia** (ergänzend, pro Kategorie in `EN_SCHWELLEN` in `config.py`, bisher nur Star Wars):
   Startkategorien in `EN_STARTKATEGORIEN` (`wikipedia/quellen.py`). Übernommen werden Themen (Wikidata-QID),
   zu denen kein deutscher Artikel den Bekanntheitsfilter besteht: Tatooine hat keinen deutschen Artikel,
   Darth Vader nur einen kurzen, kaum aufgerufenen. Seitenaufrufe und Länge werden auf en.wikipedia gemessen
   (Star Wars: mind. 100 Aufrufe/Tag, 20 Sitelinks). Das LLM erhält den
   englischen Text und formuliert die Frage auf Deutsch; die Belegstelle bleibt ein englisches Zitat.
   `quelle_url` zeigt auf en.wikipedia, in `data/verarbeitet/` stehen solche Artikel als `en:Titel`.
   Braucht Netzwerkzugriff auf `en.wikipedia.org`.
2. **Textauszug:** Einleitung und erste Abschnitte, ca. 4000 Zeichen Klartext; Abschnitte wie
   Literatur, Weblinks oder Rezeption werden übersprungen.
3. **Generierung:** Prompt wörtlich aus `SPEC.md` (`llm/prompts.py`, ein Test prüft die Übereinstimmung),
   strukturierte JSON-Ausgabe erzwungen.
4. **Prüfung:** zweiter, unabhängiger Aufruf mit gemischten Antworten, ohne Hinweis auf die richtige.
5. **Aufnahme** nur, wenn: Bekanntheit des Themas ≥ 3, Belegstelle steht im Text (ß/ss und
   Anführungszeichen normalisiert), Prüfer wählt dieselbe Antwort, eindeutig, Allgemeinwissen ≥ 3,
   formale Regeln eingehalten. Danach Deduplizierung gegen den Bestand: fast gleicher Wortlaut, dieselbe
   Tatsache mit leicht anderer Antwort („Überfall auf Polen“ / „Deutscher Überfall auf Polen“, gewichtete
   Wortüberschneidung ≥ 0.6) und Fragen, die sich gegenseitig verraten („Wer war Obamas Vizepräsident?“ ↔
   „Unter wem war Biden Vizepräsident?“). Die neuere Frage wird verworfen.

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
| `min_sitelinks` | 30 (Sport, Kunst: 50; Schweiz: 15; Star Wars: 20) | wichtigster Indikator, direkt aus SPARQL. Höher, wo Seitenaufrufe kurzlebig sind (Sport, zeitgenössische Kunst und Literatur); tiefer bei Schweizer Themen, die in wenigen Sprachen beschrieben sind |
| `min_pageviews` | 200/Tag (Naturwissenschaften, Schweiz: 100; Star Wars: 50) | abgefragtes Thema, Ø der letzten 12 vollen Monate auf de.wikipedia. Naturwissenschaftliche Artikel werden deutlich seltener aufgerufen (Niels Bohr, Enrico Fermi, Elektron < 200) |
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

## Naturwissenschafts-Templates (Wikidata)

| Template | Frage | Distraktoren |
|---|---|---|
| `element` | Welches chemische Element hat das Symbol {Fe}? / Welches chemische Symbol hat das Element {Gold}? | Elemente bis Ordnungszahl 94 mit gleichem Anfangsbuchstaben in Name oder Symbol, bekannte bevorzugt; pro Element nur eine Richtung |
| `einheit` | Welche physikalische Grösse wird in der Einheit {Watt} angegeben? / In welcher Einheit wird die {Kraft} angegeben? | andere SI-Einheiten bzw. Grössen; kuratierte Liste (Einheit → Hauptgrösse), jedes Paar gegen P111 geprüft |
| `nobelpreis` | In welchem Fachgebiet erhielt {Max Planck} den Nobelpreis? | die zwei anderen naturwissenschaftlichen Fächer und Literatur oder Frieden; nur Personen mit genau einem Nobelpreis |
| `entdeckung` | Wer entdeckte {das Elektron / Uranus / den Jupitermond Io}? | Physiker bzw. Astronomen mit ähnlichem Geburtsjahr; kuratierte Liste, nur Entdeckungen mit genau einem Entdecker (P61) |

Bewusst nicht verwendet: P61 („Entdecker oder Erfinder“) für Erfindungen und chemische Elemente –
dort stehen viele umstrittene oder falsche Angaben (Auto → Ferdinand Verbiest, Kohlenstoff → Lavoisier).
Erfindungen deckt die LLM-Pipeline mit unabhängiger Prüfung ab.

## Allgemein

Schwierigkeit: Rang nach Seitenaufrufen innerhalb des Templates (bekanntestes Drittel = 1).
Länder mit Artikel werden grammatisch korrekt eingesetzt („Hauptstadt der Schweiz“,
„Auf welchem Kontinent liegen die Bahamas?“).
