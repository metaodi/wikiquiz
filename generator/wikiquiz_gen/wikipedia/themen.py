"""Themenvielfalt: Reihenfolge der Kandidaten-Artikel so wählen, dass kein Unterthema überwiegt.

Ohne Ausgleich bestimmen allein die Seitenaufrufe, welche Artikel zuerst verarbeitet werden. In der
Geschichte sind das vor allem NS-Zeit und Zweiter Weltkrieg. Darum wird jedem Artikel ein Thema
zugeordnet und reihum aus dem Thema mit den bisher wenigsten Fragen gewählt (Bestand eingerechnet).
Innerhalb eines Themas bleibt die Reihenfolge nach Seitenaufrufen.

- Geschichte: Thema = Epoche, geschätzt aus Jahreszahlen in den Wikipedia-Kategorien
  („Geboren 1638“, „Herrscher (17. Jahrhundert)“, „Konflikt 1962“) oder dem Ereignisdatum aus Wikidata.
- Übrige Kategorien: Thema = Startkategorie, aus der der Artikel stammt („Kategorie:Oper“ …).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict, deque
from statistics import median
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")

# (bis Jahr ausschliesslich, Name)
EPOCHEN: list[tuple[float, str]] = [
    (500, "Antike"),
    (1500, "Mittelalter"),
    (1789, "Frühe Neuzeit"),
    (1914, "1789–1914"),
    (1945, "1914–1945"),
    (float("inf"), "seit 1945"),
]
THEMA_NACH_EPOCHE = {"geschichte"}
FRAGEN_PRO_ARTIKEL = 2

# Diese Stichworte in einer Wikipedia-Kategorie legen die Epoche fest. Personen der NS-Zeit lebten
# oft lange danach (Mengele 1911–1979), die Lebensmitte läge sonst nach 1945.
WELTKRIEGE = re.compile(r"(?<!\w)(nsdap|ss-|holocaust|nationalsozialis|konzentrationslager|"
                        r"(erste[rn]?|zweite[rn]?) weltkrieg)")

_VCHR = r"(?:\s*v\.\s*chr\.?)?"
_GEBOREN = re.compile(r"^geboren (?:im )?(\d{1,4})(" + _VCHR + r")$")
_GESTORBEN = re.compile(r"^gestorben (?:im )?(\d{1,4})(" + _VCHR + r")$")
_JAHRHUNDERT = re.compile(r"(\d{1,2})\. jahrhundert(" + _VCHR + r")")
# Reine Jahreskategorien („1307“) oder „Konflikt 1962“ usw. – nicht „Boeing 747“
_JAHR = re.compile(r"^(?:(?:konflikt|politik|ereignis|gegründet|aufgelöst|erbaut|erstflug|eröffnet|zerstört|"
                   r"katastrophe|vertrag|wahl) )?(\d{1,4})(" + _VCHR + r")$")


def _vorzeichen(zahl: str, vchr: str) -> int:
    return -int(zahl) if vchr.strip() else int(zahl)


def jahr_schaetzen(kategorien: Iterable[str]) -> float | None:
    """Ungefähres Jahr, in das ein Artikel gehört. Bei Personen 60 % der Lebensspanne (Staatsleute
    wirken eher in der zweiten Lebenshälfte; Lebende: Geburt + 40), sonst der Median der
    Jahreszahlen und Jahrhunderte in den Kategorien."""
    geboren = gestorben = None
    werte: list[float] = []
    for name in kategorien:
        n = name.lower().removeprefix("kategorie:").strip()
        if m := _GEBOREN.match(n):
            geboren = _vorzeichen(*m.groups())
        elif m := _GESTORBEN.match(n):
            gestorben = _vorzeichen(*m.groups())
        elif m := _JAHRHUNDERT.search(n):
            jh = _vorzeichen(*m.groups())
            werte.append(jh * 100 - 50 if jh > 0 else jh * 100 + 50)
        elif m := _JAHR.match(n):
            jahr = _vorzeichen(*m.groups())
            if -3500 <= jahr <= 2100:
                werte.append(jahr)
    if geboren is not None and gestorben is not None:
        return geboren + 0.6 * (gestorben - geboren)
    if geboren is not None:
        return geboren + 40
    if gestorben is not None:
        return gestorben - 20
    return median(werte) if werte else None


def epoche(jahr: float) -> str:
    return next(name for grenze, name in EPOCHEN if jahr < grenze)


def thema(kategorie: str, kategorien: Iterable[str], quelle: str | None, datum_jahr: int | None = None) -> str:
    if kategorie in THEMA_NACH_EPOCHE:
        kategorien = list(kategorien)
        if any(WELTKRIEGE.search(k.lower()) for k in kategorien):
            return "1914–1945"
        jahr = jahr_schaetzen(kategorien)
        if jahr is None:
            jahr = datum_jahr
        if jahr is not None:
            return epoche(jahr)
    return quelle or "unbekannt"


def ausgleichen(kandidaten: list[T], thema_von: Callable[[T], str], bestand: Counter | None = None) -> list[T]:
    """Ordnet die (nach Priorität sortierten) Kandidaten um: Als Nächstes kommt jeweils der beste
    Kandidat aus dem Thema mit den bisher wenigsten Fragen. `bestand` zählt Fragen pro Thema."""
    gruppen: dict[str, deque[T]] = defaultdict(deque)
    reihenfolge: dict[str, int] = {}
    for i, k in enumerate(kandidaten):
        t = thema_von(k)
        gruppen[t].append(k)
        reihenfolge.setdefault(t, i)
    zaehler = Counter(bestand or {})
    ergebnis: list[T] = []
    while gruppen:
        t = min(gruppen, key=lambda t: (zaehler[t], reihenfolge[t]))
        ergebnis.append(gruppen[t].popleft())
        zaehler[t] += FRAGEN_PRO_ARTIKEL
        if not gruppen[t]:
            del gruppen[t]
    return ergebnis
