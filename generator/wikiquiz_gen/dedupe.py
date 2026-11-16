"""Deduplizierung: max. N Fragen pro Quelle, fast identische Fragen entfernen.

Neben fast gleichem Wortlaut erkennt sie zwei weitere Fälle, die im selben Spiel stören:
- **dieselbe Tatsache** mit leicht anderer Antwort („Überfall auf Polen“ / „Deutscher Überfall auf
  Polen“) und ähnlichem Inhalt der Fragen,
- **gegenseitiges Verraten**: Die Antwort der einen Frage steht in der anderen und umgekehrt
  („Wer war Obamas Vizepräsident?“ ↔ „Unter wem war Biden Vizepräsident?“).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from functools import lru_cache

from .config import MAX_FRAGEN_PRO_QUELLE
from .models import Frage, normalisiere

AEHNLICHKEIT = 0.8
# Gewichteter Anteil gemeinsamer Inhaltswörter (an allen Inhaltswörtern beider Fragen) zweier Fragen
# mit (fast) gleicher Antwort, ab dem sie als dieselbe Tatsache gelten. Seltene Wörter („Polen“, „1939“) zählen mehr als häufige Fragewörter
# („Komponist“, „Land“), sonst gälten „Wer schrieb die Zauberflöte?“ und „Wer schrieb Don Giovanni?“
# als dieselbe Tatsache.
GLEICHE_TATSACHE = 0.6  # Bestand: Polen-Paar 0.66, Zauberflöte/Don Giovanni 0.49
# Anteil der Antwortwörter, die in der anderen Frage vorkommen müssen
ANTWORT_IN_FRAGE = 0.6

_FUELLWOERTER = {
    "welche", "welcher", "welches", "welchem", "welchen", "wurde", "wurden", "worden", "hatte",
    "haben", "einer", "einem", "einen", "eines", "diese", "dieser", "dieses", "nach", "durch",
    "unter", "gegen", "seit", "seine", "seiner", "ihrer", "heute", "damals", "jahr", "jahre",
    "jahrhundert", "heisst", "hiess", "nannte", "genannt", "gilt", "bekannt", "berühmt", "beim",
    "zwischen", "während", "anlässlich", "womit", "wodurch", "wofür", "wessen", "nicht", "sowie",
}


def aehnlich(a: str, b: str) -> bool:
    return SequenceMatcher(None, normalisiere(a), normalisiere(b)).ratio() >= AEHNLICHKEIT


@lru_cache(maxsize=20_000)
def inhaltswoerter(text: str) -> frozenset[str]:
    """Wörter ab 4 Zeichen ohne Füllwörter; einfache Endungen (-en, -n, -s, -e) gekürzt."""
    woerter = set()
    for w in normalisiere(text).split():
        if len(w) < 4 or w in _FUELLWOERTER:
            continue
        for endung in ("en", "n", "s", "e"):
            if len(w) > 5 and w.endswith(endung):
                w = w[: -len(endung)]
                break
        woerter.add(w)
    return frozenset(woerter)


def antwort_enthalten(a: str, b: str) -> bool:
    """Gleiche Antwort oder eine enthält die andere als Wortfolge („Überfall auf Polen“)."""
    na, nb = f" {normalisiere(a)} ", f" {normalisiere(b)} "
    return na in nb or nb in na


class Gewichte:
    """Seltenheit der Inhaltswörter (IDF) über alle Fragen eines Deduplizierungslaufs."""

    def __init__(self, fragen: list[Frage]) -> None:
        self.n = max(len(fragen), 1)
        self.df = Counter(w for f in fragen for w in inhaltswoerter(f.frage))

    def summe(self, woerter: frozenset[str]) -> float:
        return sum(math.log((self.n + 1) / (self.df.get(w, 0) + 1)) for w in woerter)


def gleiche_tatsache(a: Frage, b: Frage, gewichte: Gewichte) -> bool:
    if not antwort_enthalten(a.richtig, b.richtig):
        return False
    wa, wb = inhaltswoerter(a.frage), inhaltswoerter(b.frage)
    alle = gewichte.summe(wa | wb)
    return alle > 0 and gewichte.summe(wa & wb) / alle >= GLEICHE_TATSACHE


def kommt_vor(antwort: str, frage: str) -> bool:
    """Steht die Antwort (grösstenteils) in der Frage? Jahreszahlen zählen nicht, sie stehen oft
    nur als zeitliche Einordnung in einer Frage."""
    if normalisiere(antwort).isdigit():
        return False
    w = inhaltswoerter(antwort) or frozenset(normalisiere(antwort).split())
    if not w:
        return False
    return len(w & inhaltswoerter(frage)) / len(w) >= ANTWORT_IN_FRAGE


def verraten_sich(a: Frage, b: Frage) -> bool:
    return kommt_vor(a.richtig, b.frage) and kommt_vor(b.richtig, a.frage)


def beide_wikidata(a: Frage, b: Frage) -> bool:
    """Template-Fragen unterscheiden sich per Konstruktion im Subjekt; ähnlicher Wortlaut ist dort normal.
    Mehrfachfragen zum selben Subjekt begrenzt bereits `max_pro_quelle`."""
    return a.quelle_typ == b.quelle_typ == "wikidata"


def deduplizieren(
    fragen: list[Frage], max_pro_quelle: int = MAX_FRAGEN_PRO_QUELLE
) -> tuple[list[Frage], list[tuple[Frage, str]]]:
    """Behält die Reihenfolge bei (vorne = bevorzugt)."""
    behalten: list[Frage] = []
    verworfen: list[tuple[Frage, str]] = []
    pro_quelle: dict[str, int] = defaultdict(int)
    ids: set[str] = set()
    gewichte = Gewichte(fragen)
    for f in fragen:
        if f.id in ids:
            verworfen.append((f, "doppelte id"))
            continue
        if pro_quelle[f.quelle_id] >= max_pro_quelle:
            verworfen.append((f, f"mehr als {max_pro_quelle} fragen zu {f.quelle_id}"))
            continue
        grund = None
        for g in behalten:
            if beide_wikidata(f, g):
                continue
            if normalisiere(f.richtig) == normalisiere(g.richtig) and aehnlich(f.frage, g.frage):
                grund = f"aehnlich zu {g.id}"
            elif gleiche_tatsache(f, g, gewichte):
                grund = f"gleiche tatsache wie {g.id}"
            elif verraten_sich(f, g):
                grund = f"verraet sich gegenseitig mit {g.id}"
            if grund:
                break
        if grund:
            verworfen.append((f, grund))
            continue
        behalten.append(f)
        ids.add(f.id)
        pro_quelle[f.quelle_id] += 1
    return behalten, verworfen
