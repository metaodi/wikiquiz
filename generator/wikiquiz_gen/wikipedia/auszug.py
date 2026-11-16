"""Textauszug für das LLM: Einleitung und erste Abschnitte als Klartext (ca. 4000 Zeichen)."""
from __future__ import annotations

import re

from ..http import TAG, Http
from ..popularity import api_url

MAX_ZEICHEN = 4000
# Abschnitte ohne Fliesstext bzw. mit Nebeninformationen
UEBERSPRINGEN = {
    "literatur", "weblinks", "einzelnachweise", "anmerkungen", "siehe auch", "quellen",
    "filmografie", "diskografie", "werke", "werkverzeichnis", "auszeichnungen", "rezeption",
    "trivia", "weiterführende literatur", "fussnoten", "fußnoten", "galerie", "liste",
    # englische Wikipedia
    "references", "external links", "see also", "notes", "further reading", "bibliography",
    "sources", "citations", "footnotes", "filmography", "discography", "works", "awards",
    "reception", "gallery", "in popular culture", "merchandising", "appearances", "explanatory notes",
}
_UEBERSCHRIFT = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$")


def klartext(http: Http, titel: str, sprache: str = "de") -> str:
    res = http.json(api_url(sprache), params={
        "action": "query", "format": "json", "formatversion": "2", "prop": "extracts",
        "explaintext": "1", "exsectionformat": "wiki", "redirects": "1", "titles": titel,
    }, ttl=30 * TAG)
    seiten = res.get("query", {}).get("pages", [])
    return seiten[0].get("extract", "") if seiten else ""


def auszug(volltext: str, max_zeichen: int = MAX_ZEICHEN) -> str:
    """Einleitung + erste Abschnitte, an Absatzgrenzen gekürzt, ohne Wiki-Markup."""
    absaetze: list[str] = []
    ueberspringen = False
    for zeile in volltext.splitlines():
        m = _UEBERSCHRIFT.match(zeile.strip())
        if m:
            ebene, titel = len(m.group(1)), m.group(2)
            if ebene == 2:
                ueberspringen = titel.strip().lower() in UEBERSPRINGEN
            if not ueberspringen:
                absaetze.append(titel)
            continue
        zeile = zeile.strip()
        if zeile and not ueberspringen:
            absaetze.append(zeile)
    text = ""
    for a in absaetze:
        kandidat = f"{text}\n{a}" if text else a
        if len(kandidat) > max_zeichen:
            if not text:  # sehr langer erster Absatz: an Satzgrenze kürzen
                text = a[:max_zeichen].rsplit(". ", 1)[0] + "."
            break
        text = kandidat
    # Abschliessende Überschrift ohne Inhalt entfernen
    zeilen = text.split("\n")
    while zeilen and len(zeilen[-1]) < 60 and not zeilen[-1].endswith((".", "!", "?", ":")):
        zeilen.pop()
    return "\n".join(zeilen)
