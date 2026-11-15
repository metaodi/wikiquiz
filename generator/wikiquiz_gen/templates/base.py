"""Gemeinsame Infrastruktur für Wikidata-Templates."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from ..config import Schwellen
from ..http import Http
from ..output import Protokoll
from ..popularity import Bekanntheit, Kandidat


@dataclass
class Kontext:
    kategorie: str
    http: Http
    bekanntheit: Bekanntheit
    schwellen: Schwellen
    protokoll: Protokoll
    max_kandidaten: int = 300
    seed: int = 42

    def rng(self, *schluessel: str) -> random.Random:
        """Deterministischer Zufall pro Frage → stabile Ausgabe über Läufe."""
        return random.Random(f"{self.seed}|" + "|".join(schluessel))

    def filtern(self, kandidaten: list[Kandidat], stufe: str) -> list[Kandidat]:
        bestanden, abgelehnt = self.bekanntheit.filtern(kandidaten, self.schwellen)
        for k, grund in abgelehnt:
            self.protokoll.verwerfen(
                self.kategorie,
                f"bekanntheit:{stufe}",
                grund,
                {"qid": k.qid, "label": k.label, "titel": k.titel, "sitelinks": k.sitelinks,
                 "pageviews": None if k.pageviews is None else round(k.pageviews)},
            )
        return bestanden


def schwierigkeit_aus_pageviews(pv: float) -> int:
    """Heuristik: sehr häufig aufgerufene Themen gelten als leicht."""
    if pv >= 2500:
        return 1
    if pv >= 700:
        return 2
    return 3


def naechste_nach_bekanntheit(
    ziel_pv: float, pool: list[tuple[str, float]], rng: random.Random, n: int = 3, aus: int = 7
) -> list[str]:
    """Wählt n Einträge aus den `aus` Kandidaten mit ähnlichster Bekanntheit (log-Abstand)."""
    sortiert = sorted(pool, key=lambda e: abs(math.log1p(e[1]) - math.log1p(ziel_pv)))
    auswahl = [name for name, _ in sortiert[:aus]]
    if len(auswahl) < n:
        return []
    return rng.sample(auswahl, n)
