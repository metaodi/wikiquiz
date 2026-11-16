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
| `src/lib/kanal.ts` | Übertragungsweg für Aktionen und Spielstände; heute nur `lokalerKanal` (Pass-and-Play) |
| `src/lib/picker.ts` | Fragenauswahl: nie doppelt pro Spiel, möglichst kein zweites Mal derselbe Wikipedia-Artikel im Spiel (Fragen dazu verraten sich oft gegenseitig), zuletzt gestellte Fragen bevorzugt vermeiden |
| `src/lib/storage.ts` | `localStorage` (Spielstand, History, letzte Spieler), alles in try/catch |
| `src/screens/*` | Setup, Übergabe, Kategorie, Zufall, Frage, Feedback, Zwischenstand, Rangliste, Info |

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
- **Erschöpfte Kategorien** sind ausgegraut („keine Fragen mehr“ bzw. „bald verfügbar“); beim Antippen erscheint ein Hinweis.
  „Zufall“ wählt nur unter Kategorien mit verbleibenden Fragen. Sind alle erschöpft, endet das Spiel.
- **Quellenlink** im Feedback: „Mehr auf Wikipedia: Titel“, bei Fragen aus der englischen Wikipedia
  „Mehr auf Wikipedia (englisch): Titel“ (`src/lib/quelle.ts`). Der Titel wird mit „ss“ statt „ß“ angezeigt
  („Fussball-Weltmeisterschaft 2022“), der Link zeigt weiter auf den Originalartikel.
- **Zwischenstand** nach jeder Runde (bei mehreren Spielern); bei einem Spieler zeigt das Feedback den Punktestand.

## End-to-End-Tests (`e2e/`)

Die Tests liefern per `page.route` einen kleinen Fixture-Pool (6× Geografie, 2× Kunst, 2× Sport)
und steuern die Zeit über Playwrights Fake-Clock – Punkte und Timeouts werden exakt geprüft.

| Test | Abgedeckt |
|---|---|
| 1 Spieler | kein Übergabe-Screen, 100 P. sofort, 55 P. nach 7.5 s, falsche Antwort, Timeout, Wikipedia-Link, keine Doppelfragen, erschöpfte Kategorie mit Hinweis, Zufall nur aus offenen Kategorien, vorzeitiges Spielende, „Nochmals spielen“ |
| 4 Spieler | Übergabe an jeden Spieler, Zwischenstand mit geteilten Rängen, Zufall, Rangliste „Gleichstand“, „Neues Spiel“ mit vorbelegten Namen |
| Einstellungen | neue Kategorien bei früher „alle“ automatisch gewählt, Kategorienauswahl (Start gesperrt ohne Kategorie mit Fragen), „Immer Zufall“ ohne Kategorie-Screen und nur aus gewählten Kategorien, „Vorheriger Spieler wählt“ inkl. Zufall nach der Übergabe, Zwischenstand und Neuladen, Einstellungen gemerkt |
| Neuladen | mitten in der Frage (gleiche Frage und Reihenfolge, Timer läuft weiter, Punkte gemäss Gesamtzeit), nach Ablauf (Timeout), auf Feedback- und Übergabe-Screen |
| Timer | startet erst nach dem Einblenden, Warnfarbe ab 5 s Restzeit |
| UX | kein horizontales Scrollen bei 320 px, alle Touch-Targets ≥ 48 px, Info-Seite mit Lizenzen, kein „ß“ |

## Deployment

`.github/workflows/pages.yml` baut bei jedem Push auf `main` und veröffentlicht auf GitHub Pages.
Einmalig nötig: *Settings → Pages → Source: GitHub Actions*.
