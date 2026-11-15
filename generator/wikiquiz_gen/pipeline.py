"""Ablauf: Templates → formale Prüfung → Deduplizierung → Auswahl."""
from __future__ import annotations

import logging
from collections.abc import Callable

from .dedupe import deduplizieren
from .models import Frage
from .templates import geografie
from .templates.base import Kontext
from .validate import pruefe_formal

log = logging.getLogger(__name__)

WIKIDATA_TEMPLATES: dict[str, Callable[[Kontext], dict[str, list[Frage]]]] = {
    "geografie": geografie.generiere,
}


def reissverschluss(gruppen: dict[str, list[Frage]]) -> list[Frage]:
    """Abwechselnd aus jedem Template, jeweils die bekanntesten zuerst."""
    listen = [sorted(g, key=lambda f: -f.score) for g in gruppen.values()]
    ergebnis = []
    i = 0
    while any(i < len(l) for l in listen):
        ergebnis += [l[i] for l in listen if i < len(l)]
        i += 1
    return ergebnis


def wikidata(ktx: Kontext, ziel: int | None) -> list[Frage]:
    gen = WIKIDATA_TEMPLATES.get(ktx.kategorie)
    if gen is None:
        log.warning("Keine Wikidata-Templates für %s", ktx.kategorie)
        return []
    gruppen = gen(ktx)
    for name, fragen in gruppen.items():
        log.info("Template %-12s %4d Rohfragen", name, len(fragen))

    gueltig: dict[str, list[Frage]] = {}
    for name, fragen in gruppen.items():
        gueltig[name] = []
        for f in fragen:
            fehler = pruefe_formal(f)
            if fehler:
                ktx.protokoll.verwerfen(ktx.kategorie, "formal", "; ".join(fehler),
                                        {"frage": f.frage, "richtig": f.richtig, "falsch": f.falsch,
                                         "quelle_id": f.quelle_id})
            else:
                gueltig[name].append(f)

    sortiert = reissverschluss(gueltig)
    behalten, verworfen = deduplizieren(sortiert)
    for f, grund in verworfen:
        ktx.protokoll.verwerfen(ktx.kategorie, "dedupe", grund,
                                {"frage": f.frage, "richtig": f.richtig, "quelle_id": f.quelle_id})
    if ziel is not None:
        behalten = behalten[:ziel]
    return behalten
