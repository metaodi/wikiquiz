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
| `src/lib/picker.ts` | Fragenauswahl: nie doppelt pro Spiel, zuletzt gestellte Fragen bevorzugt vermeiden |
| `src/lib/storage.ts` | `localStorage` (Spielstand, History, letzte Spieler), alles in try/catch |
| `src/screens/*` | Setup, Übergabe, Kategorie, Zufall, Frage, Feedback, Zwischenstand, Rangliste, Info |

## Verhalten

- **Punkte:** `round(100 − 90 × t/15)` für richtige Antworten, sonst 0. Gleichstand → geteilter Rang.
- **Timer:** startet erst, wenn Frage und Antworten eingeblendet sind (`EINBLENDEN_MS`).
  Nach Neuladen oder App-Wechsel läuft er gemäss `timerStart` weiter; ist er abgelaufen, gilt die Frage als Timeout.
- **Erschöpfte Kategorien** sind ausgegraut („keine Fragen mehr“ bzw. „bald verfügbar“); beim Antippen erscheint ein Hinweis.
  „Zufall“ wählt nur unter Kategorien mit verbleibenden Fragen. Sind alle erschöpft, endet das Spiel.
- **Zwischenstand** nach jeder Runde (bei mehreren Spielern); bei einem Spieler zeigt das Feedback den Punktestand.

## End-to-End-Tests (`e2e/`)

Die Tests liefern per `page.route` einen kleinen Fixture-Pool (6× Geografie, 2× Kunst, 2× Sport)
und steuern die Zeit über Playwrights Fake-Clock – Punkte und Timeouts werden exakt geprüft.

| Test | Abgedeckt |
|---|---|
| 1 Spieler | kein Übergabe-Screen, 100 P. sofort, 55 P. nach 7.5 s, falsche Antwort, Timeout, Wikipedia-Link, keine Doppelfragen, erschöpfte Kategorie mit Hinweis, Zufall nur aus offenen Kategorien, vorzeitiges Spielende, „Nochmals spielen“ |
| 4 Spieler | Übergabe an jeden Spieler, Zwischenstand mit geteilten Rängen, Zufall, Rangliste „Gleichstand“, „Neues Spiel“ mit vorbelegten Namen |
| Neuladen | mitten in der Frage (gleiche Frage und Reihenfolge, Timer läuft weiter, Punkte gemäss Gesamtzeit), nach Ablauf (Timeout), auf Feedback- und Übergabe-Screen |
| Timer | startet erst nach dem Einblenden, Warnfarbe ab 5 s Restzeit |
| UX | kein horizontales Scrollen bei 320 px, alle Touch-Targets ≥ 48 px, Info-Seite mit Lizenzen, kein „ß“ |

## Deployment

`.github/workflows/pages.yml` baut bei jedem Push auf `main` und veröffentlicht auf GitHub Pages.
Einmalig nötig: *Settings → Pages → Source: GitHub Actions*.
