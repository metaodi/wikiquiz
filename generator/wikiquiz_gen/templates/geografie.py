"""Wikidata-Templates für die Kategorie Geografie.

Templates:
- hauptstadt: „Wie heisst die Hauptstadt von {Land}?“
- kontinent:  „Auf welchem Kontinent liegt {Land}?“
- stadt/berg/see: „In welchem Land liegt …?“
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..models import Frage, swiss
from ..popularity import Kandidat
from ..sparql import abfrage, artikel_url, qid, titel_aus_url
from .base import Kontext, naechste_nach_bekanntheit, stufen_nach_rang
from .laender import hauptstadt_von, liegt

log = logging.getLogger(__name__)

SOUVERAENER_STAAT = "Q3624078"

KONTINENTE = {
    "Q15": "Afrika",
    "Q46": "Europa",
    "Q48": "Asien",
    "Q49": "Nordamerika",
    "Q18": "Südamerika",
    "Q538": "Ozeanien",
    "Q55643": "Ozeanien",
}
# Plausible Verwechslungen pro Kontinent (Distraktoren)
KONTINENT_DISTRAKTOREN = {
    "Europa": ["Asien", "Afrika", "Nordamerika"],
    "Asien": ["Europa", "Afrika", "Ozeanien"],
    "Afrika": ["Asien", "Europa", "Südamerika"],
    "Nordamerika": ["Südamerika", "Europa", "Asien"],
    "Südamerika": ["Nordamerika", "Afrika", "Europa"],
    "Ozeanien": ["Asien", "Südamerika", "Nordamerika"],
}

# Staaten mit umstrittenem Status oder umstrittener Hauptstadt: nicht abfragen
AUSSCHLUSS_LAND = {"Q219060", "Q29999", "Q756617"}  # Palästina; Königreiche → Länder (s. u.)
# Länder, die in Wikidata nicht als souveräner Staat geführt werden (Teil eines Königreichs)
ZUSATZ_LAENDER = ["Q55", "Q35"]  # Niederlande, Dänemark
AUSSCHLUSS_HAUPTSTADT = {"Q801"}  # Israel (Jerusalem umstritten)
# Kontinentzuordnung umstritten (Kaukasus, Zypern, Landbrücken)
AUSSCHLUSS_KONTINENT = {"Q230", "Q399", "Q227", "Q229", "Q79", "Q804"}
# Gebiete mit Sonderstatus: „In welchem Land liegt …?“ wäre nicht eindeutig
SONDERGEBIETE = ["Q46395", "Q779415", "Q161243", "Q15634554", "Q1048835"]
# Wikidata ordnet Orte teils dem Königreich statt dem Land zu
KOENIGREICH_ZU_LAND = {"Q29999": "Q55", "Q756617": "Q35"}
# Höchstens so viele Fragen pro Template (triviale Templates begrenzen)
MAX_PRO_TEMPLATE = {"kontinent": 25}


@dataclass
class Land:
    k: Kandidat
    kontinente: set[str] = field(default_factory=set)  # deutsche Namen
    hauptstaedte: set[str] = field(default_factory=set)  # QIDs
    nachbarn: set[str] = field(default_factory=set)  # QIDs

    @property
    def name(self) -> str:
        return swiss(self.k.label)


def _kandidat(r: dict, item: str = "item") -> Kandidat:
    return Kandidat(
        qid=qid(r[item]),
        label=r["label"],
        titel=titel_aus_url(r["article"]),
        sitelinks=int(r["sl"]),
    )


def lade_laender(ktx: Kontext) -> dict[str, Land]:
    rows = abfrage(
        ktx.http,
        f"""
SELECT ?item ?label ?article ?sl
  (GROUP_CONCAT(DISTINCT STRAFTER(STR(?cont), "entity/")) AS ?conts)
  (GROUP_CONCAT(DISTINCT STRAFTER(STR(?cap), "entity/")) AS ?caps)
  (GROUP_CONCAT(DISTINCT STRAFTER(STR(?nb), "entity/")) AS ?nbs)
WHERE {{
  {{ ?item wdt:P31 wd:{SOUVERAENER_STAAT} }} UNION {{ VALUES ?item {{ {" ".join("wd:" + q for q in ZUSATZ_LAENDER)} }} }}
  ?item wikibase:sitelinks ?sl.
  FILTER NOT EXISTS {{ ?item wdt:P576 [] }}
  ?item rdfs:label ?label. FILTER(LANG(?label) = "de")
  ?article schema:about ?item; schema:isPartOf <https://de.wikipedia.org/>.
  OPTIONAL {{ ?item wdt:P30 ?cont }}
  OPTIONAL {{ ?item wdt:P36 ?cap }}
  OPTIONAL {{ ?item wdt:P47 ?nb }}
}} GROUP BY ?item ?label ?article ?sl
""",
    )
    alle = {}
    for r in rows:
        k = _kandidat(r)
        if k.qid in AUSSCHLUSS_LAND:
            continue
        alle[k.qid] = Land(
            k=k,
            kontinente={KONTINENTE[c] for c in r.get("conts", "").split() if c in KONTINENTE},
            hauptstaedte=set(r.get("caps", "").split()),
            nachbarn=set(r.get("nbs", "").split()),
        )
    bestanden = {k.qid for k in ktx.filtern([l.k for l in alle.values()], "land")}
    laender = {q: l for q, l in alle.items() if q in bestanden}
    for l in laender.values():
        l.nachbarn &= laender.keys()
    log.info("Länder: %d von %d bestehen den Bekanntheitsfilter", len(laender), len(alle))
    return laender


def _land_distraktoren(ktx: Kontext, land: Land, laender: dict[str, Land], *schluessel: str) -> list[str]:
    """Nachbarländer bevorzugt, sonst bekannte Länder desselben Kontinents."""
    rng = ktx.rng("land", land.k.qid, *schluessel)
    nachbarn = [laender[q] for q in sorted(land.nachbarn)]
    rng.shuffle(nachbarn)
    gewaehlt = [n.name for n in nachbarn[:3]]
    if len(gewaehlt) < 3:
        pool = sorted(
            (l for q, l in laender.items()
             if q != land.k.qid and l.kontinente & land.kontinente and l.name not in gewaehlt),
            key=lambda l: -(l.k.pageviews or 0),
        )[:10]
        gewaehlt += [l.name for l in rng.sample(pool, min(len(pool), 3 - len(gewaehlt)))]
    return gewaehlt if len(gewaehlt) == 3 else []


# ---------------------------------------------------------------------------
def hauptstadt(ktx: Kontext, laender: dict[str, Land]) -> list[Frage]:
    eindeutig = {
        q: l
        for q, l in laender.items()
        if len(l.hauptstaedte) == 1 and q not in AUSSCHLUSS_HAUPTSTADT
    }
    for q, l in laender.items():
        if len(l.hauptstaedte) > 1:
            ktx.protokoll.verwerfen(ktx.kategorie, "template:hauptstadt", "mehrere hauptstaedte",
                                    {"qid": q, "label": l.name})
    cap_qids = sorted({next(iter(l.hauptstaedte)) for l in eindeutig.values()})
    werte = " ".join(f"wd:{c}" for c in cap_qids)
    rows = abfrage(
        ktx.http,
        f"""
SELECT ?item ?label ?article ?sl WHERE {{
  VALUES ?item {{ {werte} }}
  ?item wikibase:sitelinks ?sl; rdfs:label ?label. FILTER(LANG(?label) = "de")
  ?article schema:about ?item; schema:isPartOf <https://de.wikipedia.org/>.
}}""",
    )
    staedte = {k.qid: k for k in ktx.filtern([_kandidat(r) for r in rows], "hauptstadt", antwort=True)}

    # Alle Hauptstädte (auch unbekanntere) eindeutig zuordnen: Name → Land
    fragen = []
    for q, l in eindeutig.items():
        cap = staedte.get(next(iter(l.hauptstaedte)))
        if not cap:
            continue
        pool = [
            (swiss(staedte[next(iter(m.hauptstaedte))].label), staedte[next(iter(m.hauptstaedte))].pageviews or 0)
            for mq, m in eindeutig.items()
            if mq != q and m.kontinente & l.kontinente and next(iter(m.hauptstaedte)) in staedte
        ]
        falsch = naechste_nach_bekanntheit(cap.pageviews or 0, pool, ktx.rng("hauptstadt", q))
        if not falsch:
            continue
        pv = l.k.pageviews or 0
        fragen.append(
            Frage(
                kategorie=ktx.kategorie,
                frage=f"Wie heisst die Hauptstadt {hauptstadt_von(l.name)}?",
                richtig=swiss(cap.label),
                falsch=falsch,
                schwierigkeit=2,
                quelle_typ="wikidata",
                quelle_url=artikel_url(l.k.titel),
                quelle_titel=l.k.titel,
                quelle_id=q,
                template="hauptstadt",
                score=pv,
            )
        )
    return fragen


def kontinent(ktx: Kontext, laender: dict[str, Land]) -> list[Frage]:
    fragen = []
    for q, l in laender.items():
        if len(l.kontinente) != 1 or q in AUSSCHLUSS_KONTINENT:
            continue
        richtig = next(iter(l.kontinente))
        pv = l.k.pageviews or 0
        fragen.append(
            Frage(
                kategorie=ktx.kategorie,
                frage=f"Auf welchem Kontinent {liegt(l.name)}?",
                richtig=richtig,
                falsch=list(KONTINENT_DISTRAKTOREN[richtig]),
                schwierigkeit=1,
                quelle_typ="wikidata",
                quelle_url=artikel_url(l.k.titel),
                quelle_titel=l.k.titel,
                quelle_id=q,
                template="kontinent",
                # Weniger bekannte Länder zuerst – „Wo liegt Deutschland?“ ist zu trivial
                score=-pv,
            )
        )
    return fragen


# ---------------------------------------------------------------------------
ORTSTYPEN = {
    "stadt": ["Q515", "Q1549591", "Q1637706", "Q200250"],
    "berg": ["Q8502", "Q8072"],
    "see": ["Q23397"],
}


def _formulierung(typ: str, name: str) -> str:
    if typ == "stadt":
        return f"In welchem Land liegt die Stadt {name}?"
    if typ == "berg":
        return f"In welchem Land liegt der Berg {name}?"
    if name.lower().endswith("see"):
        return f"In welchem Land liegt der {name}?"
    return f"In welchem Land liegt der See {name}?"


def ort_in_land(ktx: Kontext, laender: dict[str, Land], typ: str) -> list[Frage]:
    """Orte, die genau einem Staat zugeordnet sind (keine Grenzberge/-seen)."""
    typen = " ".join(f"wd:{t}" for t in ORTSTYPEN[typ])
    sonder = " ".join(f"wd:{t}" for t in SONDERGEBIETE)
    rows = abfrage(
        ktx.http,
        f"""
SELECT ?item ?label ?article ?sl (SAMPLE(?land) AS ?country) WHERE {{
  VALUES ?typ {{ {typen} }}
  ?item wdt:P31 ?typ; wikibase:sitelinks ?sl.
  FILTER(?sl >= {ktx.schwellen.min_sitelinks})
  FILTER NOT EXISTS {{ VALUES ?sonder {{ {sonder} }} ?item wdt:P31 ?sonder }}
  ?item wdt:P17 ?land.
  ?item rdfs:label ?label. FILTER(LANG(?label) = "de")
  ?article schema:about ?item; schema:isPartOf <https://de.wikipedia.org/>.
}} GROUP BY ?item ?label ?article ?sl
HAVING (COUNT(DISTINCT ?land) = 1)
ORDER BY DESC(?sl)
LIMIT {ktx.max_kandidaten}
""",
    )
    hauptstaedte = {c for l in laender.values() for c in l.hauptstaedte}
    kandidaten = []
    for r in rows:
        k = _kandidat(r)
        k.extra["land"] = KOENIGREICH_ZU_LAND.get(qid(r["country"]), qid(r["country"]))
        if typ == "stadt" and k.qid in hauptstaedte:
            continue  # schon über das Hauptstadt-Template abgedeckt
        if k.extra["land"] not in laender:
            ktx.protokoll.verwerfen(ktx.kategorie, f"template:{typ}", "land nicht im pool",
                                    {"qid": k.qid, "label": k.label, "land": k.extra["land"]})
            continue
        kandidaten.append(k)
    fragen = []
    for k in ktx.filtern(kandidaten, typ):
        land = laender[k.extra["land"]]
        falsch = _land_distraktoren(ktx, land, laender, typ, k.qid)
        if not falsch:
            continue
        fragen.append(
            Frage(
                kategorie=ktx.kategorie,
                frage=_formulierung(typ, swiss(k.label)),
                richtig=land.name,
                falsch=falsch,
                schwierigkeit=2,
                quelle_typ="wikidata",
                quelle_url=artikel_url(k.titel),
                quelle_titel=k.titel,
                quelle_id=k.qid,
                template=typ,
                score=k.pageviews or 0,
            )
        )
    return fragen


def generiere(ktx: Kontext) -> dict[str, list[Frage]]:
    """Gibt Fragen gruppiert nach Template zurück."""
    laender = lade_laender(ktx)
    gruppen = {
        "hauptstadt": hauptstadt(ktx, laender),
        "kontinent": kontinent(ktx, laender),
        "stadt": ort_in_land(ktx, laender, "stadt"),
        "berg": ort_in_land(ktx, laender, "berg"),
        "see": ort_in_land(ktx, laender, "see"),
    }
    for name, fragen in gruppen.items():
        fragen.sort(key=lambda f: -f.score)
        if name in MAX_PRO_TEMPLATE:
            del fragen[MAX_PRO_TEMPLATE[name]:]
        if name == "kontinent":
            for f in fragen:
                f.schwierigkeit = 1 if f.score < -1500 else 2
        else:
            stufen_nach_rang(fragen)
    return gruppen
