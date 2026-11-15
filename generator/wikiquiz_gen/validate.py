"""Formale Regeln für alle Fragen (Wikidata und LLM)."""
from __future__ import annotations

import re

from .config import MAX_ANTWORT_ZEICHEN, MAX_FRAGE_ZEICHEN
from .models import Frage, normalisiere

_WORT = re.compile(r"[^\W\d_]{4,}")
# Allgemeine Wortteile, die keinen Hinweis auf die Antwort geben
_NEUTRAL = {"stadt", "insel", "repub", "verei", "staat", "provi", "bunde"}


def verraet_antwort(frage: str, antwort: str) -> bool:
    """True, wenn ein Wortstamm (erste 5 Buchstaben eines Worts ≥ 4 Zeichen) der Antwort in der Frage vorkommt."""
    frage_n = normalisiere(frage)
    for wort in _WORT.findall(antwort.lower()):
        stamm = wort[:5]
        if stamm not in _NEUTRAL and stamm in frage_n:
            return True
    return False


def pruefe_formal(f: Frage) -> list[str]:
    """Liste der verletzten Regeln (leer = ok)."""
    fehler = []
    antworten = [f.richtig, *f.falsch]
    if len(f.falsch) != 3:
        fehler.append(f"{len(f.falsch)} distraktoren statt 3")
    if len(f.frage) > MAX_FRAGE_ZEICHEN:
        fehler.append(f"frage zu lang ({len(f.frage)})")
    for a in antworten:
        if not a.strip():
            fehler.append("leere antwort")
        if len(a) > MAX_ANTWORT_ZEICHEN:
            fehler.append(f"antwort zu lang: {a!r}")
    if len({normalisiere(a) for a in antworten}) != len(antworten):
        fehler.append("doppelte antworten")
    if any("ß" in t for t in [f.frage, *antworten]):
        fehler.append("enthaelt ß")
    if f.schwierigkeit not in (1, 2, 3):
        fehler.append(f"schwierigkeit {f.schwierigkeit}")
    if verraet_antwort(f.frage, f.richtig):
        fehler.append("frage verraet antwort")
    return fehler
