"""Wikidata-Templates für die Kategorie Kunst, Musik & Literatur.

Ein Template pro Werkart: „Wer schrieb «Die Blechtrommel»?“, „Wer malte das Gemälde
«Die Nachtwache»?“, „Wer komponierte die Oper «Carmen»?“.
Nur Werke mit genau einem Urheber. Distraktoren: Urheber anderer bekannter Werke derselben Art mit
ähnlichem Geburtsjahr (Zeitgenossen sind schwerer auszuschliessen als Personen aus anderen Jahrhunderten).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from ..config import Schwellen
from ..models import Frage, swiss
from ..popularity import Kandidat
from ..sparql import abfrage, artikel_url, qid, titel_aus_url
from .base import Kontext, stufen_nach_rang, zeitgenossen

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Werkart:
    muster: str                # SPARQL-Muster für ?item
    urheber: str               # Eigenschaft für den Urheber
    berufe: tuple[str, ...]    # Berufe (P106), einer davon muss beim Urheber stehen
    frage: str                 # Vorlage mit {titel}
    maximal: int


# Wikidata modelliert Romane und Dramen als „literarisches Werk“ (Q7725634) mit Form (P7937) und
# Opern als „dramatisch-musikalisches Werk“ mit Genre (P136) Oper. Literarische Werke werden ohne
# Gattung gefragt: Darunter sind auch Epen (Odyssee) und Theaterstücke (Faust).
WERKARTEN: dict[str, Werkart] = {
    "literatur": Werkart("?item wdt:P31 wd:Q7725634.", "P50",
                         ("Q36180", "Q6625963", "Q214917", "Q49757"),  # Schriftsteller, Romancier, Dramatiker, Dichter
                         "Wer schrieb «{titel}»?", 35),
    "gemaelde": Werkart("?item wdt:P31 wd:Q3305213.", "P170", ("Q1028181",),  # Gemälde; Maler
                        "Wer malte das Gemälde «{titel}»?", 25),
    "oper": Werkart("?item wdt:P136 wd:Q1344.", "P86", ("Q36834",),          # Genre Oper; Komponist
                    "Wer komponierte die Oper «{titel}»?", 20),
}
# Für ein Familienquiz ungeeignet
AUSSCHLUSS = {"Der Ursprung der Welt"}
# Höchstens so viele Werke pro Urheber, sonst heisst die Antwort ständig Shakespeare oder Verdi
MAX_PRO_URHEBER = 2
# Werke werden seltener aufgerufen als ihre Urheber (Die Nachtwache ≈ 150/Tag, Woyzeck ≈ 120/Tag)
SCHWELLEN_WERK = Schwellen(min_sitelinks=30, min_pageviews=80.0, min_zeichen=2000)


def _kandidat(r: dict) -> Kandidat:
    return Kandidat(qid=qid(r["item"]), label=r["label"], titel=titel_aus_url(r["article"]), sitelinks=int(r["sl"]))


def geburtsjahr(datum: str | None) -> int | None:
    """„1564-04-23T00:00:00Z“ → 1564, „-0496-01-01T…“ → -496 (Sophokles). Unbekannte Werte liefert
    Wikidata als URL (…/.well-known/genid/…) → None."""
    m = re.fullmatch(r"(-?)(\d{1,4})-\d\d-\d\dT.*", datum or "")
    if not m:
        return None
    return -int(m.group(2)) if m.group(1) else int(m.group(2))


def urheber_pool(rows: list[dict]) -> list[tuple[str, int]]:
    """Alle Urheber bekannter Werke dieser Art als Distraktoren-Pool (Name, Geburtsjahr). Besser als
    ein Pool nach Beruf (P106): Dort stehen auch Schauspieler oder Musiker, die einmal Regie führten
    oder malten (Whoopi Goldberg, Cher als „Filmregisseur“)."""
    pool: dict[str, tuple[str, int]] = {}
    for r in rows:
        jahr = geburtsjahr(r.get("geboren"))
        if jahr is not None:
            pool.setdefault(r["person"], (swiss(r["pl"]), jahr))
    return sorted(pool.values())


def werke(ktx: Kontext, name: str, art: Werkart) -> list[Frage]:
    """Der Urheber muss einen der Berufe der Werkart haben: Das schliesst u. a. Bibelbücher aus
    („Römer“ → Paulus von Tarsus), die Wikidata ebenfalls als literarische Werke führt."""
    berufe = " ".join(f"wd:{b}" for b in art.berufe)
    rows = abfrage(ktx.http, f"""
SELECT ?item ?label ?article ?sl ?person ?pl ?geboren (COUNT(DISTINCT ?p2) AS ?n) WHERE {{
  {art.muster}
  ?item wdt:{art.urheber} ?person; wdt:{art.urheber} ?p2.
  ?person wdt:P31 wd:Q5; rdfs:label ?pl. FILTER(LANG(?pl) = "de")
  FILTER EXISTS {{ VALUES ?beruf {{ {berufe} }} ?person wdt:P106 ?beruf }}
  OPTIONAL {{ ?person wdt:P569 ?geboren }}
  ?item wikibase:sitelinks ?sl. FILTER(?sl >= {SCHWELLEN_WERK.min_sitelinks})
  ?item rdfs:label ?label. FILTER(LANG(?label) = "de")
  ?article schema:about ?item; schema:isPartOf <https://de.wikipedia.org/>.
}} GROUP BY ?item ?label ?article ?sl ?person ?pl ?geboren""", ttl=30 * 86400)
    urheber: dict[str, tuple[str, int]] = {}
    for r in rows:
        q = qid(r["item"])
        if r["n"] != "1" or geburtsjahr(r.get("geboren")) is None:
            ktx.protokoll.verwerfen(ktx.kategorie, f"template:{name}", "nicht genau ein urheber mit geburtsjahr",
                                    {"qid": q, "label": r["label"]})
            continue
        urheber.setdefault(q, (swiss(r["pl"]), geburtsjahr(r["geboren"])))
    kandidaten = {qid(r["item"]): r for r in rows if qid(r["item"]) in urheber and r["label"] not in AUSSCHLUSS}
    bekannt = ktx.filtern([_kandidat(r) for r in kandidaten.values()], name, schwellen=SCHWELLEN_WERK)
    pool = urheber_pool(rows)
    fragen: list[Frage] = []
    pro_urheber: dict[str, int] = {}
    for k in sorted(bekannt, key=lambda k: -(k.pageviews or 0)):
        person, jahr = urheber[k.qid]
        if pro_urheber.get(person, 0) >= MAX_PRO_URHEBER:
            continue
        titel = swiss(k.label)
        falsch = zeitgenossen(pool, jahr, {person}, ktx.rng(name, k.qid))
        if not falsch:
            continue
        pro_urheber[person] = pro_urheber.get(person, 0) + 1
        fragen.append(Frage(
            kategorie=ktx.kategorie, frage=art.frage.format(titel=titel), richtig=person, falsch=falsch,
            schwierigkeit=2, quelle_typ="wikidata", quelle_url=artikel_url(k.titel), quelle_titel=k.titel,
            quelle_id=k.qid, template=name, score=k.pageviews or 0,
        ))
    return fragen


def generiere(ktx: Kontext) -> dict[str, list[Frage]]:
    gruppen = {name: werke(ktx, name, art) for name, art in WERKARTEN.items()}
    for name, fragen in gruppen.items():
        fragen.sort(key=lambda f: -f.score)
        del fragen[WERKARTEN[name].maximal:]
        stufen_nach_rang(fragen)
    return gruppen
