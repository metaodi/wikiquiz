"""Wikidata-Templates für die Kategorie Schweiz.

Templates:
- hauptort: „Wie heisst der Hauptort des Kantons Tessin?“ → Bellinzona (Lugano, Locarno …)
- gemeinde: „In welchem Kanton liegt Zermatt?“ → Wallis (Nachbarkantone als Distraktoren)
- berg / see: „In welchem Kanton liegt der Berg …?“ (nur bei genau einem Kanton)
- sprache: „Welche Amtssprache hat der Kanton Waadt?“ (nur einsprachige französisch- oder
  italienischsprachige Kantone; deutschsprachige wären zu einfach) und eine Frage zum
  dreisprachigen Kanton Graubünden
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..config import Schwellen
from ..models import Frage, swiss
from ..popularity import Kandidat
from ..sparql import abfrage, artikel_url, qid, titel_aus_url
from .base import Kontext, stufen_nach_rang

log = logging.getLogger(__name__)

KANTON = "Q23058"
GEMEINDE = "Q70208"
BERG = "Q8502"
SEE = "Q23397"

# Wikidata führt teils Varietäten (Schweizer Hochdeutsch, Schweizer Französisch, Bündnerromanisch);
# für die Frage zählt die Landessprache. Zuordnung über die deutsche Bezeichnung.
def landessprache(bezeichnung: str) -> str | None:
    b = bezeichnung.lower()
    for teil, sprache in (("romanisch", "Rätoromanisch"), ("deutsch", "Deutsch"),
                          ("französisch", "Französisch"), ("italienisch", "Italienisch")):
        if teil in b:
            return sprache
    return None


ALLE_SPRACHEN = ["Deutsch", "Französisch", "Italienisch", "Rätoromanisch"]

# Berge und Seen haben weniger Sprachversionen und Aufrufe als Gemeinden, auch bekannte wie
# Pilatus oder Walensee. Mit den Schwellen der Kategorie blieben im Testlauf nur 4 Berge und 3 Seen.
SCHWELLEN_NATUR = Schwellen(min_sitelinks=10, min_pageviews=40.0, min_zeichen=1500)

MAX_PRO_TEMPLATE = {"hauptort": 20, "gemeinde": 30, "berg": 15, "see": 15, "sprache": 6}
# Distraktoren für den Hauptort: die grössten anderen Gemeinden des Kantons
GEMEINDEN_PRO_KANTON = 6


@dataclass
class Kanton:
    k: Kandidat
    hauptorte: set[str] = field(default_factory=set)
    sprachen: set[str] = field(default_factory=set)
    nachbarn: set[str] = field(default_factory=set)
    gemeinden: list[tuple[str, int]] = field(default_factory=list)  # (Name, Einwohner)

    @property
    def name(self) -> str:
        """„Kanton Tessin“ → „Tessin“"""
        return swiss(self.k.label).removeprefix("Kanton ")

    @property
    def genitiv(self) -> str:
        return f"des Kantons {self.name}"


def _kandidat(r: dict) -> Kandidat:
    return Kandidat(qid=qid(r["item"]), label=r["label"], titel=titel_aus_url(r["article"]), sitelinks=int(r["sl"]))


def _artikel_teil(var: str = "item") -> str:
    return f"""?{var} wikibase:sitelinks ?sl. ?{var} rdfs:label ?label. FILTER(LANG(?label) = "de")
  ?article schema:about ?{var}; schema:isPartOf <https://de.wikipedia.org/>."""


def _frage(ktx: Kontext, k: Kandidat, frage: str, richtig: str, falsch: list[str], template: str,
           score: float) -> Frage:
    return Frage(
        kategorie=ktx.kategorie, frage=frage, richtig=richtig, falsch=falsch, schwierigkeit=2,
        quelle_typ="wikidata", quelle_url=artikel_url(k.titel), quelle_titel=k.titel, quelle_id=k.qid,
        template=template, score=score,
    )


def lade_kantone(ktx: Kontext) -> dict[str, Kanton]:
    """Alle Kantone, auch unbekanntere: Sie dienen als Antworten und Distraktoren."""
    rows = abfrage(ktx.http, f"""
SELECT ?item ?label ?article ?sl
  (GROUP_CONCAT(DISTINCT STRAFTER(STR(?cap), "entity/")) AS ?caps)
  (GROUP_CONCAT(DISTINCT ?spLabel; separator="|") AS ?sps)
  (GROUP_CONCAT(DISTINCT STRAFTER(STR(?nb), "entity/")) AS ?nbs)
WHERE {{
  ?item wdt:P31 wd:{KANTON}.
  {_artikel_teil()}
  OPTIONAL {{ ?item wdt:P36 ?cap }}
  OPTIONAL {{ ?item wdt:P37 ?sp. ?sp rdfs:label ?spLabel. FILTER(LANG(?spLabel) = "de") }}
  OPTIONAL {{ ?item wdt:P47 ?nb. ?nb wdt:P31 wd:{KANTON} }}
}} GROUP BY ?item ?label ?article ?sl""")
    kantone = {}
    for r in rows:
        if not r.get("caps"):
            continue  # historische Gebilde wie Unterwalden (ohne Hauptort), keine heutigen Kantone
        k = _kandidat(r)
        kantone[k.qid] = Kanton(
            k=k,
            hauptorte=set(r.get("caps", "").split()),
            sprachen={sp for b in r.get("sps", "").split("|") if (sp := landessprache(b))},
            nachbarn=set(r.get("nbs", "").split()),
        )
    # Kantone sind alle Allgemeinwissen: kein Bekanntheitsfilter, Schwierigkeit nach Sitelinks
    log.info("Kantone: %d", len(kantone))
    return kantone


def _orte(ktx: Kontext, klasse: str, kantone: dict[str, Kanton], mit_einwohnern: bool = False) -> list[dict]:
    """Objekte einer Klasse in der Schweiz mit allen Kantonen, in denen sie liegen."""
    einwohner = "OPTIONAL { ?item wdt:P1082 ?ew }" if mit_einwohnern else ""
    return abfrage(ktx.http, f"""
SELECT ?item ?label ?article ?sl (MAX(?ew) AS ?einwohner)
  (GROUP_CONCAT(DISTINCT STRAFTER(STR(?kanton), "entity/")) AS ?kantone)
WHERE {{
  ?item wdt:P31 wd:{klasse}; wdt:P17 wd:Q39.
  FILTER NOT EXISTS {{ ?item wdt:P576 [] }}
  ?item wdt:P131+ ?kanton. ?kanton wdt:P31 wd:{KANTON}.
  {_artikel_teil()}
  {einwohner}
}} GROUP BY ?item ?label ?article ?sl""", ttl=30 * 86400)


def _kanton_distraktoren(ktx: Kontext, kanton: Kanton, kantone: dict[str, Kanton], *schluessel: str) -> list[str]:
    """Nachbarkantone bevorzugt (Zermatt: Bern, Tessin, Uri statt Genf), sonst beliebige."""
    rng = ktx.rng("kanton", kanton.k.qid, *schluessel)
    nachbarn = sorted(kantone[q].name for q in kanton.nachbarn if q in kantone)
    rng.shuffle(nachbarn)
    gewaehlt = nachbarn[:3]
    if len(gewaehlt) < 3:
        rest = sorted(kt.name for q, kt in kantone.items() if q != kanton.k.qid and kt.name not in gewaehlt)
        gewaehlt += rng.sample(rest, 3 - len(gewaehlt))
    return gewaehlt


# ---------------------------------------------------------------------------
def hauptort(ktx: Kontext, kantone: dict[str, Kanton], gemeinden: list[dict]) -> list[Frage]:
    """Nur Kantone, deren Hauptort nicht schon im Namen steckt (Kanton Bern → Bern wäre trivial;
    das prüft die formale Regel „frage verraet antwort“). Distraktoren: grösste andere Gemeinden
    desselben Kantons, also z. B. Lugano und Locarno für das Tessin."""
    namen = {qid(r["item"]): swiss(r["label"]) for r in gemeinden}
    for r in gemeinden:
        ks = r["kantone"].split()
        if len(ks) == 1 and ks[0] in kantone and r.get("einwohner"):
            kantone[ks[0]].gemeinden.append((qid(r["item"]), int(float(r["einwohner"]))))
    fragen = []
    for q, kt in kantone.items():
        if len(kt.hauptorte) != 1:
            ktx.protokoll.verwerfen(ktx.kategorie, "template:hauptort", "nicht genau ein hauptort",
                                    {"qid": q, "label": kt.name})
            continue
        ort = next(iter(kt.hauptorte))
        if ort not in namen:
            continue
        if namen[ort].lower() in kt.name.lower():
            # Kanton Zug → Zug: Die formale Regel prüft erst Wörter ab 4 Zeichen
            ktx.protokoll.verwerfen(ktx.kategorie, "template:hauptort", "hauptort im kantonsnamen",
                                    {"qid": q, "label": kt.name})
            continue
        groesste = [namen[g] for g, _ in sorted(kt.gemeinden, key=lambda e: -e[1]) if g != ort]
        groesste = [n for n in groesste if n != namen[ort]][:GEMEINDEN_PRO_KANTON]
        if len(groesste) < 3:
            continue
        falsch = ktx.rng("hauptort", q).sample(groesste[:4], 3)
        fragen.append(_frage(ktx, kt.k, f"Wie heisst der Hauptort {kt.genitiv}?", namen[ort], falsch,
                             "hauptort", kt.k.sitelinks))
    return fragen


def im_kanton(ktx: Kontext, kantone: dict[str, Kanton], rows: list[dict], template: str,
              vorlage: str, schwellen: Schwellen | None = None) -> list[Frage]:
    """„In welchem Kanton liegt …?“ – nur Orte in genau einem Kanton und mit bekanntem Artikel.
    Hauptorte fallen weg: „In welchem Kanton liegt Aarau?“ und „Wie heisst der Hauptort des
    Kantons Aargau?“ verrieten sich gegenseitig."""
    hauptorte = {h for kt in kantone.values() for h in kt.hauptorte}
    eindeutig = {qid(r["item"]): r for r in rows
                 if len(r["kantone"].split()) == 1 and r["kantone"] in kantone and qid(r["item"]) not in hauptorte}
    bekannt = ktx.filtern([_kandidat(r) for r in eindeutig.values()], template, schwellen=schwellen)
    fragen = []
    for k in bekannt:
        kanton = kantone[eindeutig[k.qid]["kantone"]]
        name = swiss(k.label)
        falsch = _kanton_distraktoren(ktx, kanton, kantone, template)
        fragen.append(_frage(ktx, k, vorlage.format(name=name), kanton.name, falsch, template,
                             k.pageviews or 0))
    return fragen


def sprache(ktx: Kontext, kantone: dict[str, Kanton]) -> list[Frage]:
    fragen = []
    for q, kt in kantone.items():
        if kt.sprachen in ({"Französisch"}, {"Italienisch"}):
            richtig = next(iter(kt.sprachen))
            falsch = [s for s in ALLE_SPRACHEN if s != richtig]
            fragen.append(_frage(ktx, kt.k, f"Welche Amtssprache hat der Kanton {kt.name}?", richtig, falsch,
                                 "sprache", kt.k.sitelinks))
    # Der einzige dreisprachige Kanton; Distraktoren sind die zweisprachigen
    drei = [kt for kt in kantone.values() if len(kt.sprachen) == 3]
    zwei = sorted(kt.name for kt in kantone.values() if len(kt.sprachen) == 2)
    if len(drei) == 1 and len(zwei) >= 3:
        kt = drei[0]
        fragen.append(_frage(ktx, kt.k, "Welcher Kanton hat drei Amtssprachen?", kt.name,
                             ktx.rng("sprache", "drei").sample(zwei, 3), "sprache",
                             kt.k.sitelinks))
    return fragen


def generiere(ktx: Kontext) -> dict[str, list[Frage]]:
    kantone = lade_kantone(ktx)
    gemeinden = _orte(ktx, GEMEINDE, kantone, mit_einwohnern=True)
    gruppen = {
        "hauptort": hauptort(ktx, kantone, gemeinden),
        "gemeinde": im_kanton(ktx, kantone, gemeinden, "gemeinde", "In welchem Kanton liegt die Gemeinde {name}?"),
        "berg": im_kanton(ktx, kantone, _orte(ktx, BERG, kantone), "berg", "In welchem Kanton liegt der Berg {name}?",
                          SCHWELLEN_NATUR),
        "see": im_kanton(ktx, kantone, _orte(ktx, SEE, kantone), "see", "In welchem Kanton liegt der {name}?",
                        SCHWELLEN_NATUR),
        "sprache": sprache(ktx, kantone),
    }
    for name, fragen in gruppen.items():
        fragen.sort(key=lambda f: -f.score)
        del fragen[MAX_PRO_TEMPLATE[name]:]
        stufen_nach_rang(fragen)
    return gruppen
