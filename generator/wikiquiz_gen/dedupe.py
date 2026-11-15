"""Deduplizierung: max. N Fragen pro Quelle, fast identische Fragen entfernen."""
from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher

from .config import MAX_FRAGEN_PRO_QUELLE
from .models import Frage, normalisiere

AEHNLICHKEIT = 0.8


def aehnlich(a: str, b: str) -> bool:
    return SequenceMatcher(None, normalisiere(a), normalisiere(b)).ratio() >= AEHNLICHKEIT


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
    nach_antwort: dict[str, list[Frage]] = defaultdict(list)
    ids: set[str] = set()
    for f in fragen:
        if f.id in ids:
            verworfen.append((f, "doppelte id"))
            continue
        if pro_quelle[f.quelle_id] >= max_pro_quelle:
            verworfen.append((f, f"mehr als {max_pro_quelle} fragen zu {f.quelle_id}"))
            continue
        aehnliche = [
            g for g in nach_antwort[normalisiere(f.richtig)]
            if not beide_wikidata(f, g) and aehnlich(f.frage, g.frage)
        ]
        if aehnliche:
            verworfen.append((f, f"aehnlich zu {aehnliche[0].id}"))
            continue
        behalten.append(f)
        ids.add(f.id)
        pro_quelle[f.quelle_id] += 1
        nach_antwort[normalisiere(f.richtig)].append(f)
    return behalten, verworfen
