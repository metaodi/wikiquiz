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
    dedupe.py        max. 2 pro Quelle, max. 2 gleiche Antworten, ähnliche Fragen
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

## Mehrere Geräte (Konzept, teilweise umgesetzt)

Ziel: Spiel zwischen Spielern mit eigenen Geräten, am selben Tisch wie auch remote, weiterhin ohne eigenes Backend
(statische Seite auf GitHub Pages).

- **Host-autoritativ:** Das eröffnende Gerät hält den `Spielstand` und wendet als einziges die reinen Funktionen aus
  `game.ts` an. Gäste schicken Aktionen (z. B. `{ typ: 'antworten', index, zeit }`), der Host verteilt nach jeder
  Änderung den ganzen Spielstand.
- **Keine Fragen übertragen:** Alle Geräte laden dieselbe `questions.json`; übertragen werden nur `frageId` und
  `reihenfolge`. Beim Beitritt wird eine Prüfsumme der Fragen verglichen (PWA-Cache kann veraltet sein).
- **Antwortzeit misst der Gast lokal** ab Anzeige der Frage; der Host prüft nur auf `ZEITLIMIT_S` plus Toleranz.
  Kein Schutz gegen Schummeln (die Lösung steht ohnehin in `questions.json`).
- **Reconnect:** Raum, Teilnehmer und (beim Host) Spielstand liegen pro Tab im `sessionStorage` (`wikiquiz:raum:v1`,
  Geräte-ID `wikiquiz:geraet:v1`) – so bleiben mehrere Tabs im selben Browser getrennte Geräte, und ein Spiel im Raum
  überschreibt nicht das gespeicherte Spiel auf einem Gerät. Gäste klopfen mit `hallo` an, bis der Host antwortet, und
  erhalten den aktuellen Stand. Neue Geräte nur in der Lobby. Fällt der Host aus, pausiert das Spiel.
- **Zuständigkeit:** `raum.ts` bestimmt pro Phase das bedienende Gerät (`zustaendig`): Übergabe, Zufall, Frage → aktiver
  Spieler; Kategorie → Wählender; Feedback → wer dran war; Zwischenstand, Rangliste → Host. Der Host verwirft Aktionen
  anderer Geräte (`darf`); Zeitablauf darf jeder melden, beenden darf der Host immer. Der Host überwacht den Timer selbst.
- **Transport hinter einer Schnittstelle** `Kanal { senden, beiEmpfang }` mit den Umsetzungen
  lokal (heutiges Pass-and-Play), `BroadcastChannel` (mehrere Tabs, für E2E-Tests mit mehreren Seiten) und WebRTC.
- **WebRTC über Trystero:** Signalisierung über öffentliche Relays (Nostr/MQTT/BitTorrent-Tracker), danach direkte,
  verschlüsselte Datenkanäle. Beitritt per Raumcode, QR-Code oder Link (`#raum=…`). Auch am Tisch braucht der
  Verbindungsaufbau Internet, weil Browser keine Geräte im lokalen Netz finden können.
- **Neuer Spielmodus „Alle gleichzeitig“:** alle beantworten dieselbe Frage, Punkte nach Zeit. Erst damit bringen
  mehrere Geräte spielerisch einen echten Mehrwert; reihum bleibt als Variante (statt `Uebergabe` „X ist dran“).

Etappen:

1. ✅ Aktionen als Nachrichten (`app/src/lib/aktionen.ts`, `aktionAnwenden(stand, aktion, { pool, history, jetzt, rng })`)
   und `Kanal`-Schnittstelle (`app/src/lib/kanal.ts`); Pass-and-Play läuft unverändert über den lokalen Kanal.
2. ✅ Raum, Lobby und Host-Logik über `BroadcastChannel` (`app/src/lib/raum.ts`, `broadcastKanal`), reihum gespielt;
   E2E-Tests mit zwei Tabs und gemeinsamer Fake-Clock (`app/e2e/mehrgeraete.spec.ts`). Vorschau hinter `?mehrgeraete`.
   Antwortzeit misst vorerst der Host (im selben Browser gleichwertig).
3. ✅ Ablauf „Alle gleichzeitig“ (`Einstellungen.ablauf`, nur im Raum, dort Standard): Eine Runde ist eine Frage für alle,
   `Zug.alle` hält die Antwort pro Spieler; Feedback, sobald alle geantwortet haben oder die Zeit abläuft. Welcher Spieler
   antwortet, bestimmt der Host aus dem Gerät (`Kontext.spieler`), nie aus der Nachricht. Frage bedienen alle (`ALLE`),
   Feedback der Host. Gespeicherte Spielstände ohne `ablauf` gelten als „reihum“ (Schlüssel bleibt `v1`).
4. Trystero, Raumcode/QR/Link; Antwortzeit misst der Gast, Prüfsumme der Fragen beim Beitritt; Einstieg ohne `?mehrgeraete`.
5. Nur falls es in der Praxis hakt (Mobilfunk mit CGNAT): TURN-Server ergänzen oder auf ein kleines Backend
   (Cloudflare Durable Object / PartyKit) wechseln – dank `Kanal` ein Austausch an einer Stelle.

Verworfen bzw. zurückgestellt: SDP-Austausch per QR-Code (zwei Scans pro Gast, remote unbrauchbar), PeerJS
(gleiche NAT-Grenzen, Gratis-Server ohne Garantie), Firebase/Supabase/Ably (Konto bei Drittanbieter nötig).

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
| Artikel in mehreren Kategorien | Ein Artikel liefert nur in einer Kategorie Fragen: Hat eine andere Kategorie schon Fragen zur selben QID, wird er übersprungen (Lauf 19 und 20 scheiterten an wortgleichen Fragen zu Hesse bzw. Kaki in zwei Kategorien) |
| Gleiche Antworten | Pro Kategorie höchstens 2 Fragen mit derselben richtigen Antwort (ohne Jahreszahlen und Wikidata-Templates). In Lauf 12 und 14 kamen George Lucas 7×, Hogwarts, Muggel und Horkruxe je 3× vor, meist als dieselbe Tatsache in anderer Formulierung |
| Englische Wikipedia | Ergänzende Quelle pro Kategorie (`EN_SCHWELLEN`, bisher Star Wars und Harry Potter), nur für Themen, zu denen kein deutscher Artikel den Bekanntheitsfilter besteht. Das LLM formuliert die Fragen auf Deutsch, die Belegstelle bleibt englisch. Eigene Bekanntheitsschwellen, weil en.wikipedia viel mehr Seitenaufrufe hat |
| Neue Kategorien | Gespeicherte Auswahl „alle“ wird um neue Kategorien ergänzt (`bekannteKategorien`), Schlüsselversion bleibt `v1` |
| Automatisierung | GitHub Action „Fragen generieren“: pro Kategorie ein Pull Request im Modus „ergänzen“ mit Stichprobe |
| Themenvielfalt | Wikipedia-Artikel werden reihum nach Thema verarbeitet (Geschichte: Epoche aus Jahreszahlen der Wikipedia-Kategorien, sonst Startkategorie), statt nur nach Seitenaufrufen |
| Aktuelle Politik | Lebende Personen mit laufendem Amt (Wikidata P39 ohne Enddatum, Beginn ≤ 20 Jahre) werden nicht verarbeitet |
| Gleiche Quelle | Die App stellt Fragen zum selben Artikel (`quelle_url`) im selben Spiel erst, wenn keine anderen mehr übrig sind; so verraten sich Fragen zum selben Thema nicht gegenseitig |
| Nischenwissen | Pro Kategorie eine von Hand gepflegte Artikelliste (`generator/eigene_artikel.toml`): ohne Bekanntheitsfilter, vor allen anderen und auch bei erreichtem Ziel verarbeitet; das LLM erhält einen Hinweis, die Schwellen für Bekanntheit und Allgemeinwissen entfallen, Beleg und unabhängige Prüfung bleiben |
| Mehrere Geräte | Ohne eigenes Backend: Host-Gerät hält den Spielstand, Übertragung per WebRTC (Trystero, öffentliche Signalisierung) hinter einer `Kanal`-Schnittstelle; kleines Backend erst, wenn Verbindungen in der Praxis scheitern. Details im Abschnitt „Mehrere Geräte“ |
