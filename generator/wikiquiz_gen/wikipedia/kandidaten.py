"""Kandidaten-Artikel aus Wikipedia-Kategorien und Qualitätsartikeln sammeln."""
from __future__ import annotations

import logging
from datetime import date

from ..config import THEMENKATEGORIEN
from ..http import TAG, Http
from ..popularity import API_URL, Kandidat
from ..sparql import abfrage
from .quellen import QUALITAETSKATEGORIEN, STARTKATEGORIEN, zum_thema, zuordnen

log = logging.getLogger(__name__)


def _abfrage_mit_fortsetzung(http: Http, params: dict, max_seiten: int = 10_000) -> dict[int, dict]:
    """MediaWiki-Query mit generator + continue; Seitendaten werden über alle Antworten zusammengeführt."""
    seiten: dict[int, dict] = {}
    fortsetzung: dict = {}
    while True:
        res = http.json(API_URL, params={**params, **fortsetzung}, ttl=14 * TAG)
        for p in res.get("query", {}).get("pages", []):
            ziel = seiten.setdefault(p["pageid"], {"title": p["title"], "ns": p.get("ns")})
            for k, v in p.items():
                if k == "categories":
                    ziel.setdefault("categories", []).extend(c["title"] for c in v)
                elif k == "pageviews":
                    ziel.setdefault("pageviews", {}).update(v)
                elif k == "pageprops":
                    ziel.setdefault("pageprops", {}).update(v)
                else:
                    ziel[k] = v
        if "continue" not in res or len(seiten) >= max_seiten:
            return seiten
        fortsetzung = res["continue"]


def _mitglieder(http: Http, kategorie: str, extra_props: str = "", max_artikel: int = 1500) -> dict[int, dict]:
    # Keine Seitenaufrufe hier: PageViewInfo liefert nur ca. 7 Titel pro Request.
    # Die holt der Bekanntheitsfilter später nur für Artikel mit genügend Sitelinks.
    props = "pageprops" + (f"|{extra_props}" if extra_props else "")
    params = {
        "action": "query", "format": "json", "formatversion": "2",
        "generator": "categorymembers", "gcmtitle": f"Kategorie:{kategorie}",
        "gcmtype": "page|subcat", "gcmlimit": "50",
        "prop": props, "ppprop": "wikibase_item|disambiguation",
    }
    if "categories" in props:
        params.update({"clshow": "!hidden", "cllimit": "max"})
    return _abfrage_mit_fortsetzung(http, params, max_seiten=max_artikel)


def kategorie_artikel(http: Http, kategorie: str, tiefe: int, max_artikel: int = 1500) -> list[dict]:
    """Artikel (ns 0) einer Kategorie inkl. Unterkategorien bis `tiefe`."""
    artikel: dict[str, dict] = {}
    gesehen: set[str] = set()
    offen = [(kategorie, 0)]
    while offen and len(artikel) < max_artikel:
        kat, t = offen.pop(0)
        if kat in gesehen:
            continue
        gesehen.add(kat)
        for p in _mitglieder(http, kat, max_artikel=max_artikel).values():
            if p.get("ns") == 14 and t < tiefe:
                offen.append((p["title"].removeprefix("Kategorie:"), t + 1))
            elif p.get("ns") == 0:
                artikel.setdefault(p["title"], p)
    return list(artikel.values())


def qualitaets_artikel(http: Http) -> list[dict]:
    """Exzellente und lesenswerte Artikel mit zugeordneter Quizkategorie (`zuordnung`)."""
    ergebnis = []
    for kat in QUALITAETSKATEGORIEN:
        for p in _mitglieder(http, kat, extra_props="categories", max_artikel=10_000).values():
            if p.get("ns") == 0:
                p["zuordnung"] = zuordnen(p.get("categories", []))
                p["themen"] = [t for t in sorted(THEMENKATEGORIEN) if zum_thema(p.get("categories", []), t)]
                ergebnis.append(p)
    return ergebnis


def artikel_kategorien(http: Http, titel: list[str]) -> dict[str, list[str]]:
    """Nicht versteckte Wikipedia-Kategorien pro Artikel (50 Titel pro Request)."""
    ergebnis: dict[str, list[str]] = {}
    for i in range(0, len(titel), 50):
        seiten = _abfrage_mit_fortsetzung(http, {
            "action": "query", "format": "json", "formatversion": "2", "prop": "categories",
            "clshow": "!hidden", "cllimit": "max", "titles": "|".join(titel[i : i + 50]),
        })
        for p in seiten.values():
            ergebnis[p["title"]] = p.get("categories", [])
    return ergebnis


def berufe(http: Http, qids: list[str]) -> dict[str, list[str]]:
    """Berufe (Wikidata P106) pro Objekt, 200 Objekte pro SPARQL-Abfrage."""
    ergebnis: dict[str, list[str]] = {}
    eindeutig = sorted(set(qids))
    for i in range(0, len(eindeutig), 200):
        werte = " ".join(f"wd:{q}" for q in eindeutig[i : i + 200])
        for r in abfrage(http, f"SELECT ?item ?beruf WHERE {{ VALUES ?item {{ {werte} }} ?item wdt:P106 ?beruf. }}",
                         ttl=30 * TAG):
            ergebnis.setdefault(r["item"].rsplit("/", 1)[-1], []).append(r["beruf"].rsplit("/", 1)[-1])
    return ergebnis


def passende_kategorie(http: Http, kandidaten: list[Kandidat], kategorie: str
                       ) -> tuple[list[Kandidat], list[tuple[Kandidat, str]]]:
    """Kategorie-Abgleich: Zeigen Wikipedia-Kategorien und Wikidata-Berufe eines Artikels eindeutig
    auf eine andere Quizkategorie, wird er übersprungen (z. B. Friedrich II. aus „Komponist (Klassik)“
    → Geschichte, Johannes Kepler → Naturwissenschaften). Artikel ohne eindeutige Zuordnung bleiben drin.
    Themenkategorien (Schweiz, Star Wars) liegen quer zu den Fachkategorien: dort kein Abgleich."""
    if kategorie in THEMENKATEGORIEN:
        return list(kandidaten), []
    kats = artikel_kategorien(http, [k.titel for k in kandidaten])
    b = berufe(http, [k.qid for k in kandidaten])
    behalten, verworfen = [], []
    for k in kandidaten:
        zuordnung = zuordnen(kats.get(k.titel, []), b.get(k.qid, []))
        if zuordnung is not None and zuordnung != kategorie:
            verworfen.append((k, f"kategorie passt nicht: {zuordnung}"))
        else:
            behalten.append(k)
    return behalten, verworfen


def amtierende(http: Http, qids: list[str], heute: date | None = None, jahre: int = 20) -> set[str]:
    """Lebende Personen, die laut Wikidata gerade ein Amt innehaben: eine Aussage „Position“ (P39)
    mit Beginn in den letzten `jahre` Jahren und ohne Enddatum (z. B. Bundeskanzler seit 2025).
    Fragen zu ihnen veralten schnell, der Generierungs-Prompt schliesst sie ohnehin aus.
    Ohne Beginn zählt eine Aussage nicht, weil ältere Ämter oft ohne Enddatum erfasst sind."""
    seit = (heute or date.today()).year - jahre
    ergebnis: set[str] = set()
    eindeutig = sorted(set(qids))
    for i in range(0, len(eindeutig), 200):
        werte = " ".join(f"wd:{q}" for q in eindeutig[i : i + 200])
        for r in abfrage(http, f"""
SELECT DISTINCT ?item WHERE {{
  VALUES ?item {{ {werte} }}
  ?item wdt:P31 wd:Q5. FILTER NOT EXISTS {{ ?item wdt:P570 ?tod }}
  ?item p:P39 ?aussage. ?aussage wikibase:rank ?rang; pq:P580 ?beginn.
  FILTER(?rang != wikibase:DeprecatedRank && YEAR(?beginn) >= {seit})
  FILTER NOT EXISTS {{ ?aussage pq:P582 ?ende }}
}}""", ttl=7 * TAG):
            ergebnis.add(r["item"].rsplit("/", 1)[-1])
    return ergebnis


def sitelinks(http: Http, qids: list[str]) -> dict[str, int]:
    """Anzahl Sprachversionen pro Wikidata-Objekt (SPARQL, 300 Objekte pro Abfrage)."""
    anzahl: dict[str, int] = {}
    eindeutig = sorted(set(qids))
    for i in range(0, len(eindeutig), 300):
        werte = " ".join(f"wd:{q}" for q in eindeutig[i : i + 300])
        for r in abfrage(http, f"SELECT ?item ?sl WHERE {{ VALUES ?item {{ {werte} }} ?item wikibase:sitelinks ?sl. }}",
                         ttl=30 * TAG):
            anzahl[r["item"].rsplit("/", 1)[-1]] = int(r["sl"])
    return anzahl


def ereignisdaten(http: Http, qids: list[str]) -> dict[str, date]:
    """Jüngstes Datum aus Zeitpunkt (P585), Beginn (P580) oder Veröffentlichung (P577)."""
    daten: dict[str, date] = {}
    for i in range(0, len(qids), 200):
        werte = " ".join(f"wd:{q}" for q in qids[i : i + 200])
        rows = abfrage(http, f"""
SELECT ?item (MAX(?d) AS ?datum) WHERE {{
  VALUES ?item {{ {werte} }}
  VALUES ?p {{ wdt:P585 wdt:P580 wdt:P577 }}
  ?item ?p ?d. FILTER(DATATYPE(?d) = xsd:dateTime)
}} GROUP BY ?item""")
        for r in rows:
            try:
                daten[r["item"].rsplit("/", 1)[-1]] = date.fromisoformat(r["datum"][:10])
            except ValueError:
                pass  # z. B. Jahreszahlen v. Chr.
    return daten


def sammeln(http: Http, kategorie: str, min_sitelinks: int, max_pro_quelle: int = 1500) -> list[Kandidat]:
    """Kandidaten der Quizkategorie mit mind. `min_sitelinks`, dedupliziert nach Titel.
    Seitenaufrufe, Länge usw. prüft danach der Bekanntheitsfilter."""
    roh: dict[str, dict] = {}
    for kat, tiefe in STARTKATEGORIEN.get(kategorie, []):
        artikel = kategorie_artikel(http, kat, tiefe, max_artikel=max_pro_quelle)
        if not artikel:
            log.warning("%s: Startkategorie „%s“ ist leer oder existiert nicht", kategorie, kat)
        for p in artikel:
            roh.setdefault(p["title"], {**p, "quelle": f"Kategorie:{kat}"})
    for p in qualitaets_artikel(http):
        if p.get("zuordnung") == kategorie or kategorie in p.get("themen", []):
            roh.setdefault(p["title"], {**p, "quelle": "Exzellent/Lesenswert"})
    mit_qid = {t: p for t, p in roh.items()
               if p.get("pageprops", {}).get("wikibase_item") and "disambiguation" not in p.get("pageprops", {})}
    links = sitelinks(http, [p["pageprops"]["wikibase_item"] for p in mit_qid.values()])
    bekannt = {t: p for t, p in mit_qid.items() if links.get(p["pageprops"]["wikibase_item"], 0) >= min_sitelinks}
    daten = ereignisdaten(http, [p["pageprops"]["wikibase_item"] for p in bekannt.values()])
    kandidaten = []
    for titel, p in bekannt.items():
        q = p["pageprops"]["wikibase_item"]
        k = Kandidat(qid=q, label=titel, titel=titel, sitelinks=links[q], datum=daten.get(q))
        k.extra["quelle"] = p["quelle"]
        kandidaten.append(k)
    log.info("%s: %d Artikel gefunden, %d mit mind. %d Sitelinks", kategorie, len(roh), len(kandidaten),
             min_sitelinks)
    return kandidaten
