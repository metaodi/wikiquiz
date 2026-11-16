# WikiQuiz – App

Progressive Web App (Svelte 5 + Vite + TypeScript), offline-fähig und installierbar.
Die Fragen kommen aus `public/questions.json` (vom Generator erzeugt) und werden vom
Service Worker vorab gecacht. Es gibt kein Backend.

```bash
npm install
npm run dev        # Entwicklungsserver
npm run check      # Typprüfung (svelte-check)
npm test           # Unit-Tests der Spiellogik (Vitest)
npm run e2e        # End-to-End-Tests (Playwright, Chromium, Pixel-7-Viewport)
npm run build      # Produktions-Build nach dist/ (BASE_PATH=/wikiquiz/ für GitHub Pages)
```

## Aufbau

| Datei | Inhalt |
|---|---|
| `src/lib/config.ts` | Zeitlimit (15 s), Punkteformel, Runden, Farben – zentral konfigurierbar |
| `src/lib/game.ts` | Spiellogik als reine Funktionen (Zeit und Zufall werden hereingereicht) |
| `src/lib/aktionen.ts` | Spielzüge als serialisierbare Aktionen; `aktionAnwenden` führt sie über `game.ts` aus |
| `src/lib/kanal.ts` | Übertragungsweg für Aktionen und Spielstände: `lokalerKanal` (Pass-and-Play), `broadcastKanal` (Tabs im selben Browser) |
| `src/lib/raum.ts` | Mehrere Geräte: wer welche Phase bedient (`zustaendig`, `darf`), Beitritt, Raumcode |
| `src/lib/picker.ts` | Fragenauswahl: nie doppelt pro Spiel, möglichst kein zweites Mal derselbe Wikipedia-Artikel im Spiel (Fragen dazu verraten sich oft gegenseitig), zuletzt gestellte Fragen bevorzugt vermeiden |
| `src/lib/storage.ts` | `localStorage` (Spielstand, History, letzte Spieler), alles in try/catch |
| `src/screens/*` | Setup, Übergabe, Kategorie, Zufall, Frage, Feedback, Zwischenstand, Rangliste, Info; für mehrere Geräte RaumStart, Lobby, Warten |

## Verhalten

- **Punkte:** `round(100 − 90 × t/15)` für richtige Antworten, sonst 0. Gleichstand → geteilter Rang.
- **Timer:** startet erst, wenn Frage und Antworten eingeblendet sind (`EINBLENDEN_MS`).
  Nach Neuladen oder App-Wechsel läuft er gemäss `timerStart` weiter; ist er abgelaufen, gilt die Frage als Timeout.
- **Kategorie-Wahl** (im Setup): *Selbst wählen* (Standard), *Vorheriger Spieler wählt* (ab 2 Spielern; wer gerade
  dran war, wählt vor der Übergabe die Kategorie für den Nächsten – beim ersten Zug der Letzte für den Ersten; wählt er
  „Zufall“, sieht die Animation erst der Nächste) oder *Immer Zufall* (kein Kategorie-Screen, es wird sofort gelost).
- **Kategorien** (im Setup): standardmässig alle; Abwahl einzelner Kategorien schränkt Kategorie-Screen, „Zufall“ und
  Zufalls-Animation auf die Auswahl ein. Modus und Auswahl werden wie die Spielernamen für das nächste Spiel gemerkt.
  Neu hinzugekommene Kategorien (z. B. Schweiz, Star Wars, Harry Potter) werden automatisch gewählt, wenn zuvor alle gewählt waren;
  eine bewusste Auswahl bleibt unverändert (`bekannteKategorien` in `wikiquiz:players:v1`). Die entfernte Kategorie
  „Allgemeinwissen“ fällt aus gespeicherten Auswahlen weg.
- **Schwierigkeit** (im Setup, pro Spieler): *Leicht*, *Mittel* (Standard) oder *Schwer* – entspricht `schwierigkeit`
  1/2/3 der Fragen. Gezogen wird zuerst aus der gewählten Stufe; ist sie in der Kategorie aufgebraucht, aus der
  nächstliegenden (leicht → mittel → schwer, mittel → leicht → schwer, schwer → mittel → leicht,
  `SCHWIERIGKEIT_REIHENFOLGE` in `config.ts`). Eine Kategorie bleibt so spielbar, solange sie überhaupt Fragen hat.
  Unter „Pro Kategorie anpassen“ lässt sich die Stufe pro Spieler für einzelne (gewählte) Kategorien abweichend
  setzen; ohne Anpassung gilt die Gesamtstufe. Gespeichert werden nur Abweichungen (`proKategorie` am Spieler);
  wird die Gesamtstufe geändert, fallen Abweichungen weg, die ihr nun entsprechen.
  Punkte hängen nicht von der Schwierigkeit ab. Die Wahl wird mit den Namen gemerkt (`schwierigkeiten` und
  `proKategorie` in `wikiquiz:players:v1`); ältere Spielstände ohne Wahl gelten als *Mittel*.
  Mit mehreren Geräten wählt jeder seine Stufe (inkl. „Pro Kategorie anpassen“) beim Eröffnen bzw. Beitreten
  (`SchwierigkeitWahl.svelte`); sie geht mit `hallo` an den Host, der sie prüft (`stufenWahlPruefen`) und beim
  Teilnehmer ablegt. *Reihum* gilt diese Wahl, der Host sieht sie im Setup. Bei *Alle gleichzeitig* beantworten alle
  dieselbe Frage, deshalb wählt der Host eine gemeinsame Stufe (`raumSchwierigkeit`, gemerkt); die persönliche Wahl
  ruht dann. Ältere Geräte ohne Wahl gelten als *Mittel*.
- **Erschöpfte Kategorien** sind ausgegraut („keine Fragen mehr“ bzw. „bald verfügbar“); beim Antippen erscheint ein Hinweis.
  „Zufall“ wählt nur unter Kategorien mit verbleibenden Fragen. Sind alle erschöpft, endet das Spiel.
- **Quellenlink** im Feedback: „Mehr auf Wikipedia: Titel“, bei Fragen aus der englischen Wikipedia
  „Mehr auf Wikipedia (englisch): Titel“ (`src/lib/quelle.ts`). Der Titel wird mit „ss“ statt „ß“ angezeigt
  („Fussball-Weltmeisterschaft 2022“), der Link zeigt weiter auf den Originalartikel.
- **Zwischenstand** nach jeder Runde (bei mehreren Spielern); bei einem Spieler zeigt das Feedback den Punktestand.
- **Mehrere Geräte (Beta):** „Mit mehreren Geräten spielen“ im Setup. Die Geräte verbinden sich über WebRTC
  (Trystero, `src/lib/kanal.ts` → `netzKanal`); den Verbindungsaufbau vermitteln öffentliche Nostr-Relays, Trystero wird
  erst dann als eigener Chunk geladen. Ein Gerät eröffnet einen Raum (4-stelliger Code) und leitet das Spiel (Host), bis
  zu drei weitere treten bei – per Code, per QR-Code oder Link `…/?raum=CODE` (öffnet den Beitritt mit vorausgefülltem
  Code; „Link teilen“ nutzt das Teilen-Menü bzw. die Zwischenablage). Jedes Gerät ist ein Spieler, die Farbe vergibt der
  Host. Beitreten kann nur, wer denselben Fragenstand hat (`poolKennung`), sonst erscheint die Bitte, neu zu laden.
  `?kanal=tabs` verbindet stattdessen Tabs im selben Browser (`BroadcastChannel`, für E2E-Tests und Entwicklung ohne
  Netzwerk). Klappt keine direkte Verbindung (z. B. im Mobilfunknetz), leitet ein TURN-Server von Metered weiter
  (`src/lib/turn.ts`, eingerichtet über `VITE_TURN_CREDENTIALS_URL`, siehe Deployment). „Verbindung: …“ in der
  Raumkarte und im Hinweisbalken klappt eine Diagnose auf: Relays, verbundene Geräte, TURN, direkt oder über TURN,
  letzter Fehler. Der Host wählt Ablauf,
  Runden, Modus und Kategorien und startet. Zwei Abläufe:
  - *Alle gleichzeitig* (Standard im Raum): Eine Runde ist eine Frage für alle. Die Kategorie wählt reihum ein Spieler
    für alle (bzw. Zufall; „Vorheriger Spieler wählt“ ist gesperrt), keine Übergabe. Jeder antwortet auf seinem Gerät,
    Punkte nach der eigenen Antwortzeit; wer geantwortet hat, sieht „Warte auf die anderen … (x/n)“. Das Feedback kommt,
    sobald alle geantwortet haben oder die Zeit abgelaufen ist (fehlende Antworten = Timeout): oben das eigene Ergebnis,
    darunter alle Antworten mit Punkten und Zeit. „Weiter“ hat der Host; kein Zwischenstand. Oben zeigt jedes Gerät
    die eigenen Punkte.
  - *Reihum* wie auf einem Gerät: Wer dran ist, sieht „Du bist dran“, wählt und antwortet; die anderen sehen, wer dran
    ist bzw. wählt, und schauen bei der Frage zu (Antworten gesperrt). Feedback sehen alle, „Weiter“ hat nur, wer dran
    war; Zwischenstand und Rangliste bedient der Host.

  Der Host prüft jede Aktion (`darf`) und überwacht den Timer selbst. **Zeit:** Jedes Gerät misst die Antwortzeit selbst
  und meldet sie mit; der Host übernimmt sie, solange sie höchstens `NETZ_TOLERANZ_S` (1.5 s) kürzer ist als bei ihm
  gemessen. Eine Frage schliesst er erst nach Zeitlimit plus Toleranz ab, damit unterwegs befindliche Antworten zählen.
  Die Gäste schätzen den Unterschied ihrer Uhr zum Host aus dem Zeitstempel jedes Spielstands (Maximum über alle
  Nachrichten) und zeigen den Timer danach an. **Verbindung:** Kommt ein Gerät (wieder) dazu, schickt ihm der Host den
  Stand; ohne Verbindung zu anderen Geräten erscheint ein Hinweisbalken, und in der Lobby nach 15 s ein Hinweis zur
  Fehlersuche. Neuladen: Raum und Geräte-ID liegen pro Tab im `sessionStorage`
  (`wikiquiz:raum:v1`, `wikiquiz:geraet:v1`); Gäste werden wiedererkannt, der Host führt das Spiel weiter. Neue Geräte
  können nur in der Lobby beitreten. Beendet der Host das Spiel, sind alle wieder im Raum; schliesst er den Raum, werden
  die Gäste informiert. Spiele im Raum berühren den gespeicherten Spielstand und die Spielernamen des Spiels auf einem Gerät nicht.

## End-to-End-Tests (`e2e/`)

Die Tests liefern per `page.route` einen kleinen Fixture-Pool (6× Geografie, 2× Kunst, 2× Sport)
und steuern die Zeit über Playwrights Fake-Clock – Punkte und Timeouts werden exakt geprüft.

| Test | Abgedeckt |
|---|---|
| 1 Spieler | kein Übergabe-Screen, 100 P. sofort, 55 P. nach 7.5 s, falsche Antwort, Timeout, Wikipedia-Link, keine Doppelfragen, erschöpfte Kategorie mit Hinweis, Zufall nur aus offenen Kategorien, vorzeitiges Spielende, „Nochmals spielen“ |
| 4 Spieler | Übergabe an jeden Spieler, Zwischenstand mit geteilten Rängen, Zufall, Rangliste „Gleichstand“, „Neues Spiel“ mit vorbelegten Namen |
| Einstellungen | neue Kategorien bei früher „alle“ automatisch gewählt, Kategorienauswahl (Start gesperrt ohne Kategorie mit Fragen), „Immer Zufall“ ohne Kategorie-Screen und nur aus gewählten Kategorien, „Vorheriger Spieler wählt“ inkl. Zufall nach der Übergabe, Zwischenstand und Neuladen, Einstellungen gemerkt, Schwierigkeit pro Spieler (Fragen der gewählten Stufe, Ausweichen auf die nächste, gemerkt) |
| Neuladen | mitten in der Frage (gleiche Frage und Reihenfolge, Timer läuft weiter, Punkte gemäss Gesamtzeit), nach Ablauf (Timeout), auf Feedback- und Übergabe-Screen |
| Timer | startet erst nach dem Einblenden, Warnfarbe ab 5 s Restzeit |
| UX | kein horizontales Scrollen bei 320 px, alle Touch-Targets ≥ 48 px, Info-Seite mit Lizenzen, kein „ß“ |
| Mehrere Geräte | alles mit `?kanal=tabs` (WebRTC selbst wird nicht automatisch getestet). Beitritt per Link/QR-Code (Code vorausgefüllt, Parameter verschwindet aus der Adresse), Ablehnung bei anderem Fragenstand; drei Tabs „Alle gleichzeitig“ (Timeout erst nach der Netz-Toleranz): Standard-Ablauf, gleiche Frage überall, Warten mit Zähler, Timeout für fehlende Antwort, eigene und alle Ergebnisse, Kategoriewahl reihum, eigene Punkte oben, Rangliste, „Nochmals“; Schwierigkeit reihum pro Gerät und gemeinsam bei „Alle gleichzeitig“; zwei Tabs in einem Browser-Kontext (gemeinsame Fake-Clock): Lobby, Züge reihum mit Zuschauen, Neuladen von Gast und Host, Spiel beenden → zurück in den Raum, Raum verlassen; Beitritt mit vergebenem Namen abgelehnt, Host schliesst den Raum; Einstieg nur mit `?mehrgeraete`, 320 px |
| Netz | Netz-Modus ohne echte Verbindung (Relays blockiert): TURN-Zugangsdaten werden von der Test-URL geladen (`TURN_TEST_URL` in `playwright.config.ts`), Diagnose zeigt TURN „bereit“ bzw. „nicht ladbar“ und den Relay-Fehler |

## Deployment

`.github/workflows/pages.yml` baut bei jedem Push auf `main` und veröffentlicht auf GitHub Pages.
Einmalig nötig: *Settings → Pages → Source: GitHub Actions*.

**TURN-Server (Metered) für Spiele mit mehreren Geräten** – ohne ihn scheitert die Verbindung oft, sobald ein Gerät
im Mobilfunknetz ist:

1. Konto auf [metered.ca](https://www.metered.ca/) anlegen, unter *TURN Server* eine App erstellen (Gratis-Plan genügt).
2. Unter *TURN Server → Developers* bzw. *API Keys* einen API-Key erzeugen. Die URL zum Abrufen der Zugangsdaten hat
   die Form `https://<app>.metered.live/api/v1/turn/credentials?apiKey=<KEY>`.
3. Im Dashboard die erlaubten Domains auf die Domain der App beschränken (z. B. `metaodi.ch`), damit Fremde den Key
   nicht nutzen können.
4. Auf GitHub unter *Settings → Secrets and variables → Actions* das Secret `TURN_CREDENTIALS_URL` mit dieser URL
   anlegen und den Workflow „App bauen und auf GitHub Pages veröffentlichen“ neu starten.
5. Prüfen: Raum öffnen, „Verbindung: …“ aufklappen → „TURN-Server: bereit“.

Lokal: `VITE_TURN_CREDENTIALS_URL=… npm run dev`. Fehlt die Variable, verbinden sich die Geräte ohne TURN.
