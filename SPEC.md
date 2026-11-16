# Auftrag: Mobile Quiz-App „WikiQuiz“ (Pass-and-Play, 1–4 Spieler)

## Ziel
Baue eine mobile Quiz-App, deren Fragen aus der deutschsprachigen Wikipedia und aus Wikidata stammen. Bis zu 4 Spieler spielen abwechselnd auf einem Gerät, das jeweils weitergegeben wird.

Das Projekt besteht aus zwei getrennten Teilen:

1. **Fragen-Generator** (Python-Skript, läuft offline bzw. als Build-Schritt): erzeugt einen geprüften Fragenpool als `questions.json`. Der LLM-API-Key liegt ausschliesslich hier und nie im Client.
2. **App** (Progressive Web App): lädt den Fragenpool statisch und enthält die gesamte Spiellogik. Es braucht kein Backend.

Die Fragen werden vorab generiert, nicht live während des Spiels. So entsteht keine Wartezeit, keine Kosten pro Spiel, und die Qualität kann vorab geprüft werden.

---

## Teil 1: App

### Technik
- Progressive Web App, mobile-first, offline-fähig und installierbar (Service Worker, Web App Manifest).
- Vite + TypeScript + Svelte (alternativ React, falls begründet).
- `questions.json` wird beim Build mitgeliefert und vom Service Worker gecacht.
- Spielstand in `localStorage` sichern, damit ein App-Wechsel oder Neuladen das Spiel nicht beendet. Zugriffe in try/catch kapseln.

### Kategorien
1. Naturwissenschaften & Technik
2. Kunst, Musik & Literatur
3. Geschichte
4. Sport & Unterhaltung
5. Geografie
6. Allgemeinwissen

Zusätzlich gibt es die Option **„Zufall“**: Sie wählt zufällig eine der 6 Kategorien und zeigt diese kurz an (kleine Animation), bevor die Frage erscheint.

### Spielablauf
1. **Setup:** 1–4 Spieler mit Namen und Farbe erfassen. Anzahl Runden wählbar: 5, 10 oder 15 (Standard 10). Eine Runde bedeutet: jeder Spieler beantwortet eine Frage.
2. **Übergabe-Screen** vor jedem Zug: „Gib das Gerät an {Name}“ mit Button „Bereit“, damit die anderen die Frage nicht vorher sehen. Bei nur einem Spieler entfällt dieser Screen.
3. Der aktive Spieler wählt eine Kategorie oder „Zufall“.
4. Die Frage erscheint mit 4 Antwort-Buttons in zufälliger Reihenfolge und einem sichtbaren 15-Sekunden-Timer. Der Timer startet erst, wenn Frage und Antworten vollständig angezeigt sind.
5. **Feedback** nach Antwort oder Timeout: richtig/falsch, richtige Antwort hervorgehoben, erhaltene Punkte, Link „Mehr auf Wikipedia“ (öffnet den Quellartikel).
6. Weiter zum nächsten Spieler. Zwischen den Runden ist ein kurzer Zwischenstand sichtbar.
7. Nach der letzten Runde: **Rangliste** mit Siegerehrung und Optionen „Nochmals spielen“ (gleiche Spieler) und „Neues Spiel“.

Regeln:
- Eine Frage wird innerhalb eines Spiels nie zweimal gestellt.
- Über mehrere Spiele hinweg werden zuletzt gestellte Frage-IDs in `localStorage` gemerkt und bevorzugt vermieden.
- Ist eine Kategorie erschöpft, wird das dem Spieler angezeigt und er wählt eine andere.

### Punkte
- Richtige Antwort: maximal 100 Punkte, abnehmend mit der Antwortzeit `t` (Sekunden, gemessen ab Timer-Start):
  `punkte = round(100 − 90 × (t / 15))`
  Also 100 Punkte bei sofortiger Antwort und 10 Punkte kurz vor Ablauf.
- Falsche Antwort oder keine Antwort nach 15 Sekunden: 0 Punkte.
- Die Formel und die Zeitlimite zentral und konfigurierbar implementieren.
- Bei Punktegleichstand am Ende teilen sich die Spieler den Rang.

### UX
- Mobile-first, im Hochformat einhändig bedienbar, grosse Touch-Targets (mind. 48 px).
- Eigene Farbe und Icon pro Kategorie.
- Timer als schrumpfender Balken, der die letzten 5 Sekunden farblich hervorhebt.
- Kurzes haptisches Feedback über die Vibration API, wo verfügbar.
- Gut lesbar auch bei langen Antworten (Umbruch statt Abschneiden).
- UI-Sprache Deutsch mit Schweizer Rechtschreibung (immer „ss“, nie „ß“).
- Info-Seite mit Quellen- und Lizenzhinweis.

---

## Teil 2: Fragen-Generator

### Überblick
Der Generator kombiniert zwei Quellen und schreibt alles in `questions.json`:

- **A) Wikidata-Templates:** faktenbasierte Fragen ohne LLM.
- **B) Wikipedia-Artikel + LLM:** vielfältigere Fragen, mit unabhängiger Prüfung.

Ziel: mindestens 150 geprüfte Fragen pro Kategorie.

### Allgemein für alle Wikimedia-Abfragen
- Aussagekräftigen User-Agent mit Kontaktangabe setzen.
- Rate Limits respektieren, Antworten lokal cachen, damit wiederholte Läufe die APIs nicht erneut belasten.

### Bekanntheitsfilter (gilt für A und B)
Es sollen nur einigermassen bekannte Themen verwendet werden, damit kein Nischenwissen abgefragt wird. Kandidaten werden zuerst mit harten Kennzahlen gefiltert:

- **Sprachversionen (Wikidata-Sitelinks):** mindestens 30. Das ist der wichtigste Indikator.
- **Seitenaufrufe auf de.wikipedia** (Wikimedia Pageviews API): im Schnitt mindestens 200 pro Tag über die letzten 12 Monate.
- **Ausschliessen:** Listen, Begriffsklärungen, Artikel zu Ereignissen, die weniger als 1 Jahr zurückliegen, sowie Stubs unter 3000 Zeichen.
- Die Schwellen sind pro Kategorie konfigurierbar. Bei Sport & Unterhaltung sind die Seitenaufrufe oft hoch, aber kurzlebig, daher dort einen strengeren Sitelink-Filter verwenden (z. B. mindestens 50).

### A) Wikidata-Templates (SPARQL)
Template-Fragen pro Kategorie, zum Beispiel:
- Geografie: „Was ist die Hauptstadt von {Land}?“, „In welchem Land liegt {Berg/See/Stadt}?“
- Naturwissenschaften & Technik: „Welches chemische Element hat das Symbol {X}?“, „Wer erfand {Erfindung}?“
- Kunst, Musik & Literatur: „Wer schrieb {Werk}?“, „Wer komponierte {Werk}?“, „Wer malte {Gemälde}?“
- Geschichte: „In welchem Jahr {Ereignis}?“, „Wer war {Amt} während {Ereignis}?“

Regeln:
- Distraktoren aus derselben Klasse ziehen (andere Hauptstädte derselben Region, andere Autoren derselben Epoche, Jahreszahlen im Abstand von 5–50 Jahren).
- Distraktoren müssen eindeutig falsch sein (z. B. keine Ko-Autoren, keine Länder mit mehreren Hauptstädten).
- Bekanntheitsfilter auf das abgefragte Element und auf die richtige Antwort anwenden.
- Deutsche Labels verwenden. Elemente ohne deutsches Label überspringen.

### B) Wikipedia-Artikel + LLM

**Artikelauswahl:** Kandidaten aus thematisch passenden Kategorien der deutschsprachigen Wikipedia sowie aus „Exzellente Artikel“ und „Lesenswerte Artikel“ holen, dann den Bekanntheitsfilter anwenden.

**Textauszug:** Dem LLM nur Einleitung und die ersten Abschnitte übergeben (ca. 4000 Zeichen, Klartext ohne Wiki-Markup). So kann es gar nicht erst nach Details aus hinteren Abschnitten fragen.

**Generierungs-Prompt:** Genau wie folgt verwenden (strukturierte JSON-Ausgabe erzwingen):

~~~
# SYSTEM

Du bist Redaktor:in für eine Quiz-App für Familien und Freundesgruppen
im deutschsprachigen Raum (Zielgruppe: interessierte Laien ab ca. 12 Jahren).
Du erstellst Multiple-Choice-Fragen auf Basis eines Wikipedia-Artikels.

## Grundsätze
1. Allgemeinwissen statt Nischenwissen. Frage nach dem, wofür das
   Thema bekannt ist (Kernaussage aus der Einleitung), nicht nach
   Details, Nebenfiguren oder exakten Zahlen aus hinteren Abschnitten.
   Test: Würde eine gebildete Person, die das Thema nicht studiert hat,
   die Antwort plausibel kennen oder herleiten können?
2. Belegt. Die richtige Antwort muss sich eindeutig aus dem gelieferten
   Text ergeben. Zitiere die Belegstelle wörtlich (max. 25 Wörter).
3. Eindeutig. Genau eine Antwort ist richtig, auch nach strenger
   Lesart. Keine Fragen, deren Antwort umstritten ist oder sich bald ändert
   (amtierende Personen, aktuelle Rekorde, „grösste/neueste …“ ohne Zeitbezug).
4. Selbsterklärend. Die Frage ist ohne den Artikel verständlich und
   verrät die Antwort nicht (kein Wortstamm der Antwort in der Frage).
5. Kurz. Frage max. 120 Zeichen, jede Antwort max. 40 Zeichen.

## Regeln für die falschen Antworten (Distraktoren)
- Genau 3, gleicher Typ wie die richtige Antwort (Person ↔ Person,
  Jahr ↔ Jahr, Stadt ↔ Stadt) und ähnliche Länge und Form.
- Plausibel für jemanden, der es nicht genau weiss, aber eindeutig falsch.
- Nach Möglichkeit aus demselben Themenfeld (andere Komponisten derselben
  Epoche, Nachbarländer, Jahreszahlen im Abstand von 5–50 Jahren).
- Verboten: „Alle genannten“, „Keine davon“, Witzantworten, Verneinungen.

## Schwierigkeit
1 = die meisten Erwachsenen wissen es
2 = gutes Allgemeinwissen nötig
3 = Kenner:innen wissen es, andere können es herleiten
Fragen, die schwieriger als 3 wären, nicht erstellen.

## Sprache
Deutsch mit Schweizer Rechtschreibung (immer „ss“, nie „ß“),
neutral und ohne Fachjargon.
Ist der Artikeltext englisch, formuliere Frage und Antworten trotzdem
auf Deutsch (mit den im deutschsprachigen Raum üblichen Namen und
Titeln). Die Belegstelle zitierst du wörtlich im englischen Original.

## Ausgabe
Antworte ausschliesslich mit gültigem JSON nach diesem Schema:

{
  "bekanntheit_thema": 1-5,
  "fragen": [
    {
      "frage": "string",
      "richtige_antwort": "string",
      "falsche_antworten": ["string", "string", "string"],
      "schwierigkeit": 1-3,
      "belegstelle": "wörtliches Zitat aus dem Text",
      "begruendung_bekanntheit": "1 Satz, warum das Allgemeinwissen ist"
    }
  ]
}

bekanntheit_thema: 5 = weltbekannt, 3 = im deutschsprachigen Raum
geläufig, 1 = Fachpublikum. Ist das Thema unter 3 oder lässt der Text
keine gute Frage zu, gib "fragen": [] zurück. Eine leere Liste ist
besser als eine schwache Frage.

## Beispiele
GUT: „Welcher Komponist schrieb die Oper ‚Die Zauberflöte‘?“
 → Mozart | Beethoven, Haydn, Schubert
SCHLECHT: „In welchem Jahr wurde Mozarts Schwester Nannerl geboren?“
 → Nebenfigur, Detailwissen
SCHLECHT: „Was ist die Zauberflöte?“ → Eine Oper | ein Instrument, …
 → Distraktoren nicht plausibel, zu trivial

# USER

Kategorie: {kategorie}
Gewünschte Anzahl Fragen: bis zu {n} (Standard: 2)
Bereits vorhandene Fragen zu diesem Thema (nicht wiederholen):
{bestehende_fragen}

Artikeltitel: {titel}
Artikeltext (Einleitung und erste Abschnitte):
"""
{text}
"""
~~~

**Prüf-Prompt:** Jede generierte Frage in einem zweiten, unabhängigen LLM-Call prüfen. Der Prüfer sieht die Antworten gemischt und erfährt NICHT, welche als richtig markiert ist:

~~~
Du prüfst eine Quizfrage. Du siehst NICHT, welche Antwort als richtig
markiert ist.

Frage: {frage}
Antworten (gemischt): {a}, {b}, {c}, {d}
Artikelauszug: """{text}"""

Antworte als JSON:
{
  "deine_antwort": "string",
  "eindeutig": true/false,
  "allgemeinwissen": 1-5,
  "probleme": ["string"]
}
~~~

**Aufnahme in den Pool** nur, wenn alle Bedingungen erfüllt sind:
- `bekanntheit_thema` ist mindestens 3.
- Die `belegstelle` kommt tatsächlich im Artikeltext vor (programmatisch prüfen).
- `deine_antwort` des Prüfers stimmt mit der markierten richtigen Antwort überein.
- `eindeutig` ist `true`.
- `allgemeinwissen` ist mindestens 3.
- Formale Regeln eingehalten (Längen, genau 3 Distraktoren, keine doppelten Antworten, kein „ß“).

Verworfene Fragen mit Grund in `rejected.jsonl` protokollieren, damit sich die Schwellen nachjustieren lassen.

### Deduplizierung
- Pro Artikel bzw. Wikidata-Element höchstens 2 Fragen im Pool.
- Fast identische Fragen (gleiche richtige Antwort und ähnlicher Fragetext) entfernen.

### Datenformat `questions.json`
Pro Frage:
- `id` (stabil, z. B. Hash aus Quelle und Fragetext)
- `kategorie`
- `frage`
- `antworten` (Array mit 4 Einträgen, Reihenfolge wird zur Laufzeit gemischt)
- `korrekt_index`
- `schwierigkeit` (1–3)
- `quelle_typ` (`wikidata` oder `wikipedia`)
- `quelle_url`
- `lizenz` (`CC BY-SA 4.0` für Wikipedia-Inhalte, `CC0` für Wikidata)

### Bedienung des Generators
- CLI mit Optionen für Kategorie, Zielanzahl, Schwellenwerte und Trockenlauf.
- Einen Review-Modus anbieten, der pro Kategorie eine Stichprobe (z. B. 30 Fragen) lesbar als Markdown ausgibt, damit ich die Qualität vor dem vollen Lauf prüfen kann.
- LLM-Modell und API-Key über Umgebungsvariablen konfigurieren.

---

## Rechtliches
- Quellenangabe pro Frage (Wikipedia-Link) im Feedback-Screen.
- Lizenzhinweise auf der Info-Seite (Wikipedia: CC BY-SA 4.0, Wikidata: CC0).

---

## Vorgehen
1. Schlage zuerst Architektur, Ordnerstruktur und Datenmodell vor und warte auf meine Bestätigung.
2. Implementiere den Wikidata-Generator mit Bekanntheitsfilter für eine Kategorie (Geografie) als Proof of Concept und zeige mir eine Stichprobe.
3. Ergänze die LLM-Pipeline (Generierung und Prüfung) und zeige mir eine Stichprobe pro Kategorie.
4. Baue die App gegen den erzeugten Fragenpool.
5. Teste den Spielablauf mit 1 und mit 4 Spielern, inklusive Timeout, falscher Antwort, App-Neuladen mitten im Spiel und erschöpfter Kategorie.
