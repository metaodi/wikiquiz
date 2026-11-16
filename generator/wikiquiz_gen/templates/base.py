"""Gemeinsame Infrastruktur für Wikidata-Templates."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace

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

    def filtern(self, kandidaten: list[Kandidat], stufe: str, antwort: bool = False,
                bekanntheit: Bekanntheit | None = None, schwellen: Schwellen | None = None) -> list[Kandidat]:
        """antwort=True: Schwelle für richtige Antworten (min_pageviews_antwort) verwenden.
        `bekanntheit`/`schwellen` übersteuern die Standardwerte (z. B. für en.wikipedia)."""
        schwellen = schwellen or self.schwellen
        if antwort:
            schwellen = replace(schwellen, min_pageviews=schwellen.min_pageviews_antwort)
        bestanden, abgelehnt = (bekanntheit or self.bekanntheit).filtern(kandidaten, schwellen)
        for k, grund in abgelehnt:
            self.protokoll.verwerfen(
                self.kategorie,
                f"bekanntheit:{stufe}",
                grund,
                {"qid": k.qid, "label": k.label, "titel": k.schluessel, "sitelinks": k.sitelinks,
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


def stufen_nach_rang(fragen: list, stufen: tuple[int, ...] = (1, 2, 3)) -> None:
    """Schwierigkeit nach Bekanntheitsrang innerhalb eines Templates (bekannteste Drittel = leicht)."""
    sortiert = sorted(fragen, key=lambda f: -f.score)
    for i, f in enumerate(sortiert):
        f.schwierigkeit = stufen[min(len(stufen) - 1, i * len(stufen) // max(1, len(sortiert)))]


def personen_nach_beruf(ktx: Kontext, berufe: list[str], min_sitelinks: int = 100) -> list[tuple[str, int]]:
    """Bekannte Personen mit einem der Berufe (Wikidata P106) als (Name, Geburtsjahr) – Pool für
    Distraktoren wie „Wer schrieb …?“ oder „Wer führte Regie …?“."""
    from ..models import swiss
    from ..sparql import abfrage

    werte = " ".join(f"wd:{b}" for b in berufe)
    rows = abfrage(ktx.http, f"""
SELECT DISTINCT ?p ?pl ?jahr WHERE {{
  VALUES ?beruf {{ {werte} }}
  ?p wdt:P106 ?beruf; wdt:P569 ?geboren; wikibase:sitelinks ?sl. FILTER(?sl >= {min_sitelinks})
  ?p rdfs:label ?pl. FILTER(LANG(?pl) = "de") BIND(YEAR(?geboren) AS ?jahr)
}}""", ttl=30 * 86400)
    gesehen: dict[str, tuple[str, int]] = {}
    for r in rows:
        if r.get("jahr"):
            gesehen.setdefault(r["p"], (swiss(r["pl"]), int(r["jahr"])))
    return sorted(gesehen.values())


def zeitgenossen(pool: list[tuple[str, int]], jahr: int, ausser: set[str], rng: random.Random,
                 n: int = 3, aus: int = 6) -> list[str]:
    """n Personen aus den `aus` mit dem ähnlichsten Geburtsjahr (ohne `ausser`)."""
    kandidaten = sorted((p for p in pool if p[0] not in ausser), key=lambda p: (abs(p[1] - jahr), p[0]))
    namen = list(dict.fromkeys(name for name, _ in kandidaten))[:aus]
    return rng.sample(namen, n) if len(namen) >= n else []
