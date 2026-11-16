"""Wikidata-Templates für die Kategorie Sport & Unterhaltung.

Templates:
- olympia:    „In welcher Stadt fanden die Olympischen Sommerspiele 1972 statt?“ → München
               (Distraktoren: Austragungsorte zeitlich naher Spiele derselben Art; Städte kuratiert)
- wm_land:    „In welchem Land fand die Fussball-Weltmeisterschaft 2006 statt?“ → Deutschland
- wm_sieger:  „Welches Land gewann die Fussball-Weltmeisterschaft 2014?“ → Deutschland
               (Distraktoren: andere Weltmeister und Finalisten)
- film:       „Wer führte Regie beim Film «Der weisse Hai»?“ → Steven Spielberg
               (Distraktoren: Regisseure anderer bekannter Filme mit ähnlichem Geburtsjahr)
"""
from __future__ import annotations

import logging
import re

from ..config import Schwellen
from ..models import Frage, swiss
from ..popularity import Kandidat
from ..sparql import abfrage, artikel_url, qid, titel_aus_url
from .base import Kontext, stufen_nach_rang, zeitgenossen
from .kunst import geburtsjahr, urheber_pool

log = logging.getLogger(__name__)

SOMMERSPIELE = "Q159821"
WINTERSPIELE = "Q82414"
FUSSBALL_WM = "Q19317"
FILM = "Q11424"

# Gastgeberstädte: In Wikidata uneinheitlich erfasst (P131 nur bei wenigen Spielen, P276 meist mit
# Stadien), darum kuratiert. Spiele mit mehreren Gastgeberstädten (Mailand/Cortina 2026) fehlen.
SOMMER_ORTE = {
    1896: "Athen", 1900: "Paris", 1904: "St. Louis", 1908: "London", 1912: "Stockholm", 1920: "Antwerpen",
    1924: "Paris", 1928: "Amsterdam", 1932: "Los Angeles", 1936: "Berlin", 1948: "London", 1952: "Helsinki",
    1956: "Melbourne", 1960: "Rom", 1964: "Tokio", 1968: "Mexiko-Stadt", 1972: "München", 1976: "Montreal",
    1980: "Moskau", 1984: "Los Angeles", 1988: "Seoul", 1992: "Barcelona", 1996: "Atlanta", 2000: "Sydney",
    2004: "Athen", 2008: "Peking", 2012: "London", 2016: "Rio de Janeiro", 2020: "Tokio", 2024: "Paris",
}
WINTER_ORTE = {
    1924: "Chamonix", 1928: "St. Moritz", 1932: "Lake Placid", 1936: "Garmisch-Partenkirchen",
    1948: "St. Moritz", 1952: "Oslo", 1956: "Cortina d’Ampezzo", 1960: "Squaw Valley", 1964: "Innsbruck",
    1968: "Grenoble", 1972: "Sapporo", 1976: "Innsbruck", 1980: "Lake Placid", 1984: "Sarajevo",
    1988: "Calgary", 1992: "Albertville", 1994: "Lillehammer", 1998: "Nagano", 2002: "Salt Lake City",
    2006: "Turin", 2010: "Vancouver", 2014: "Sotschi", 2018: "Pyeongchang", 2022: "Peking",
}
# Wikidata nennt als Gastgeber der WM 1966 das Vereinigte Königreich; ausgerichtet hat sie England
LAND_ANZEIGE = {"Vereinigtes Königreich": "England"}

MAX_PRO_TEMPLATE = {"olympia": 25, "wm_land": 12, "wm_sieger": 12, "film": 30}
# Filme: nur sehr bekannte (viele Sprachversionen); ältere Klassiker werden selten aufgerufen
SCHWELLEN_FILM = Schwellen(min_sitelinks=60, min_pageviews=100.0, min_zeichen=2000)
# Spiele und Turniere: Ältere Ausgaben (Olympia 1936, WM 1954) werden selten aufgerufen,
# sind aber Allgemeinwissen. Die Sitelinks sind dort hoch.
SCHWELLEN_TURNIER = Schwellen(min_sitelinks=40, min_pageviews=50.0, min_zeichen=2000)


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


def _jahr(label: str) -> int | None:
    m = re.search(r"\b(18|19|20)\d\d\b", label)
    return int(m.group()) if m else None


def _nahe(eintraege: list[tuple[int, str]], jahr: int, ausser: set[str], ktx: Kontext, *schluessel: str,
          aus: int = 6) -> list[str]:
    """3 Namen von zeitlich nahen Einträgen (Jahr, Name), ohne Duplikate und ohne `ausser`."""
    namen = list(dict.fromkeys(n for j, n in sorted(eintraege, key=lambda e: (abs(e[0] - jahr), e[1]))
                               if n not in ausser))[:aus]
    return ktx.rng(*schluessel).sample(namen, 3) if len(namen) >= 3 else []


# ---------------------------------------------------------------------------
def olympia(ktx: Kontext) -> list[Frage]:
    """Artikel und Bekanntheit aus Wikidata, Gastgeberstadt aus der kuratierten Liste."""
    fragen = []
    for art, orte in ((SOMMERSPIELE, SOMMER_ORTE), (WINTERSPIELE, WINTER_ORTE)):
        rows = abfrage(ktx.http, f"""
SELECT ?item ?label ?article ?sl WHERE {{
  ?item wdt:P3450 wd:{art}.
  {_artikel_teil()}
}}""", ttl=30 * 86400)
        spiele = [(r, _jahr(r["label"])) for r in rows if r["label"].startswith("Olympische ")]
        spiele = [(r, j) for r, j in spiele if j in orte]
        alle_orte = sorted(orte.items())
        bekannt = {k.qid for k in ktx.filtern([_kandidat(r) for r, _ in spiele], "olympia",
                                               schwellen=SCHWELLEN_TURNIER)}
        for r, jahr in spiele:
            k = _kandidat(r)
            if k.qid not in bekannt:
                continue
            ort = orte[jahr]
            falsch = _nahe(alle_orte, jahr, {ort}, ktx, "olympia", k.qid)
            if not falsch:
                continue
            spiele_dativ = "die Olympischen " + swiss(r["label"]).removeprefix("Olympische ")
            fragen.append(_frage(ktx, k, f"In welcher Stadt fanden {spiele_dativ} statt?", ort, falsch,
                                 "olympia", int(r["sl"])))
    return fragen


def _wm_ausgaben(ktx: Kontext) -> list[dict]:
    """Vergangene Fussball-WM der Männer mit Gastgeberland(-ländern) und Sieger (als Land)."""
    return abfrage(ktx.http, f"""
SELECT ?item ?label ?article ?sl
  (GROUP_CONCAT(DISTINCT ?landLabel; separator="|") AS ?laender)
  (GROUP_CONCAT(DISTINCT ?siegerLabel; separator="|") AS ?sieger)
WHERE {{
  ?item wdt:P3450 wd:{FUSSBALL_WM}.
  OPTIONAL {{ ?item wdt:P17 ?land. ?land rdfs:label ?landLabel. FILTER(LANG(?landLabel) = "de") }}
  OPTIONAL {{ ?item wdt:P1346 ?team. ?team wdt:P1532 ?sl2. ?sl2 rdfs:label ?siegerLabel.
             FILTER(LANG(?siegerLabel) = "de") }}
  {_artikel_teil()}
}} GROUP BY ?item ?label ?article ?sl""", ttl=30 * 86400)


def _wm_name(label: str) -> str | None:
    """„Fußball-Weltmeisterschaft 2014“ → „Fussball-Weltmeisterschaft 2014“ (nur Männer-WM)"""
    name = swiss(label)
    return name if re.fullmatch(r"Fussball-Weltmeisterschaft (19|20)\d\d", name) else None


def wm(ktx: Kontext) -> tuple[list[Frage], list[Frage]]:
    # Nur ausgetragene Turniere: Sieger bekannt (1942/1946 fielen aus, 2030 liegt in der Zukunft)
    rows = [r for r in _wm_ausgaben(ktx) if _wm_name(r["label"]) and r["sieger"]]
    for r in rows:
        r["laender"] = "|".join(LAND_ANZEIGE.get(swiss(l), swiss(l)) for l in r["laender"].split("|") if l)
    bekannt = {k.qid for k in ktx.filtern([_kandidat(r) for r in rows], "wm", schwellen=SCHWELLEN_TURNIER)}
    gastgeber = [(_jahr(r["label"]), swiss(r["laender"])) for r in rows if r["laender"] and "|" not in r["laender"]]
    sieger_alle = sorted({swiss(s) for r in rows for s in r["sieger"].split("|") if s})
    land_fragen, sieger_fragen = [], []
    for r in rows:
        k = _kandidat(r)
        if k.qid not in bekannt:
            continue
        name, jahr = _wm_name(r["label"]), _jahr(r["label"])
        if r["laender"] and "|" not in r["laender"]:  # nicht 2002 (Japan und Südkorea)
            land = swiss(r["laender"])
            falsch = _nahe(gastgeber, jahr, {land}, ktx, "wm_land", k.qid)
            if falsch:
                land_fragen.append(_frage(ktx, k, f"In welchem Land fand die {name} statt?", land, falsch,
                                          "wm_land", int(r["sl"])))
        sieger = [swiss(s) for s in r["sieger"].split("|") if s]
        if len(sieger) == 1:
            andere = [s for s in sieger_alle if s != sieger[0]]
            if len(andere) >= 3:
                falsch = ktx.rng("wm_sieger", k.qid).sample(andere, 3)
                sieger_fragen.append(_frage(ktx, k, f"Welches Land gewann die {name}?", sieger[0], falsch,
                                            "wm_sieger", int(r["sl"])))
    return land_fragen, sieger_fragen


def film(ktx: Kontext) -> list[Frage]:
    rows = abfrage(ktx.http, f"""
SELECT ?item ?label ?article ?sl ?person ?pl ?geboren (COUNT(DISTINCT ?p2) AS ?n) WHERE {{
  ?item wdt:P31 wd:{FILM}; wdt:P57 ?person; wdt:P57 ?p2.
  ?person wdt:P31 wd:Q5; rdfs:label ?pl. FILTER(LANG(?pl) = "de") ?person wdt:P569 ?geboren.
  ?item wikibase:sitelinks ?sl. FILTER(?sl >= {SCHWELLEN_FILM.min_sitelinks})
  ?item rdfs:label ?label. FILTER(LANG(?label) = "de")
  ?article schema:about ?item; schema:isPartOf <https://de.wikipedia.org/>.
}} GROUP BY ?item ?label ?article ?sl ?person ?pl ?geboren""", ttl=30 * 86400)
    eindeutig = {qid(r["item"]): r for r in rows if r["n"] == "1" and geburtsjahr(r["geboren"]) is not None}
    regie = {q: (swiss(r["pl"]), geburtsjahr(r["geboren"])) for q, r in eindeutig.items()}
    bekannt = ktx.filtern([_kandidat(r) for r in eindeutig.values()], "film", schwellen=SCHWELLEN_FILM)
    # Regisseure bekannter Filme (60+ Sprachversionen), nicht alle Personen mit Beruf „Filmregisseur“
    pool = urheber_pool(rows)
    fragen, pro_person = [], {}
    for k in sorted(bekannt, key=lambda k: -(k.pageviews or 0)):
        person, jahr = regie[k.qid]
        if pro_person.get(person, 0) >= 2:  # sonst ständig Spielberg
            continue
        falsch = zeitgenossen(pool, jahr, {person}, ktx.rng("film", k.qid))
        if not falsch:
            continue
        pro_person[person] = pro_person.get(person, 0) + 1
        fragen.append(_frage(ktx, k, f"Wer führte Regie beim Film «{swiss(k.label)}»?", person, falsch,
                             "film", k.pageviews or 0))
    return fragen


def generiere(ktx: Kontext) -> dict[str, list[Frage]]:
    wm_land, wm_sieger = wm(ktx)
    gruppen = {"olympia": olympia(ktx), "wm_land": wm_land, "wm_sieger": wm_sieger, "film": film(ktx)}
    for name, fragen in gruppen.items():
        fragen.sort(key=lambda f: -f.score)
        del fragen[MAX_PRO_TEMPLATE[name]:]
        stufen_nach_rang(fragen)
    return gruppen
