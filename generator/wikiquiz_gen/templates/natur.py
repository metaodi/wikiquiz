"""Wikidata-Templates für die Kategorie Tiere & Natur.

Templates (jedes Tier kommt nur in einem davon vor, sonst verrieten sich die Fragen):
- tierklasse: „Zu welcher Tiergruppe gehört der Blauwal?“ → Säugetiere (Fische, Vögel, Reptilien)
- welches_tier: „Welches dieser Tiere ist ein Säugetier?“ → Schnabeltier (Waran, Strauss, Hai)

Die Klasse wird über die Taxonomie bestimmt: Elterntaxon (P171) paketweise nach oben verfolgen, bis
eine der bekannten Klassen erreicht ist. Eine Pfadabfrage (P171+) läuft in die Zeitbegrenzung.
Den grammatischen Artikel („der Blauwal“, „die Hauskatze“) liefert der erste Satz des Wikipedia-Artikels;
Tiere ohne eindeutigen Artikel im Singular werden nur im Template `welches_tier` verwendet.
"""
from __future__ import annotations

import logging
import re

from ..config import Schwellen
from ..http import TAG
from ..models import Frage, swiss
from ..popularity import API_URL, Kandidat
from ..sparql import abfrage, artikel_url, qid, titel_aus_url
from .base import Kontext, stufen_nach_rang

log = logging.getLogger(__name__)

ART = "Q7432"
# Wikidata-Klasse → Tiergruppe in der Frage. Knochen- und Knorpelfische zählen beide als „Fische“.
KLASSEN = {
    "Q7377": "Säugetiere", "Q5113": "Vögel", "Q10811": "Reptilien", "Q10908": "Amphibien",
    "Q127282": "Fische", "Q25371": "Fische", "Q1390": "Insekten", "Q1358": "Spinnentiere",
}
# Plausible Verwechslungen (Wal → Fische, Pinguin → Säugetiere, Salamander → Reptilien …)
VERWECHSLUNG = {
    "Säugetiere": ["Fische", "Vögel", "Reptilien", "Amphibien"],
    "Vögel": ["Säugetiere", "Reptilien", "Fische", "Insekten"],
    "Reptilien": ["Amphibien", "Säugetiere", "Fische", "Vögel"],
    "Amphibien": ["Reptilien", "Fische", "Säugetiere", "Insekten"],
    "Fische": ["Säugetiere", "Amphibien", "Reptilien", "Vögel"],
    "Insekten": ["Spinnentiere", "Amphibien", "Vögel", "Reptilien"],
    "Spinnentiere": ["Insekten", "Reptilien", "Amphibien", "Säugetiere"],
}
EINZAHL = {"Säugetiere": "ein Säugetier", "Vögel": "ein Vogel", "Reptilien": "ein Reptil",
           "Amphibien": "eine Amphibie", "Fische": "ein Fisch", "Insekten": "ein Insekt",
           "Spinnentiere": "ein Spinnentier"}

MAX_PRO_TEMPLATE = {"tierklasse": 25, "welches_tier": 15}
# Höchstens so viele Fragen pro Tiergruppe und Template, sonst fast nur Säugetiere und Vögel
MAX_PRO_KLASSE = 6
SCHWELLEN_TIER = Schwellen(min_sitelinks=60, min_pageviews=80.0, min_zeichen=2000)
_ARTIKEL = re.compile(r"^(Der|Die|Das)\s+(.+?)\s*(\(.*?\))?\s*(?:,[^,]*,)?\s*(ist|war|gehört|zählt)\b")


def _kandidat(r: dict) -> Kandidat:
    """Name = Titel des deutschen Artikels ohne Klammerzusatz (Label ist teils wissenschaftlich)."""
    titel = titel_aus_url(r["article"])
    return Kandidat(qid=qid(r["item"]), label=re.sub(r"\s*\(.*\)$", "", titel), titel=titel,
                    sitelinks=int(r["sl"]))


def bekannte_arten(ktx: Kontext) -> list[dict]:
    """Arten mit deutschem Trivialnamen (P1843) und vielen Sprachversionen. Der Trivialname grenzt die
    Abfrage stark ein: Alle Arten mit vielen Sprachversionen abzufragen läuft in die Zeitbegrenzung.
    Pflanzen sind auch dabei; sie fallen beim Bestimmen der Tiergruppe weg."""
    return abfrage(ktx.http, f"""
SELECT DISTINCT ?item ?article ?sl WHERE {{
  ?item wdt:P1843 ?name. FILTER(LANG(?name) = "de")
  ?item wdt:P105 wd:{ART}; wikibase:sitelinks ?sl. FILTER(?sl >= {SCHWELLEN_TIER.min_sitelinks})
  ?article schema:about ?item; schema:isPartOf <https://de.wikipedia.org/>.
}}""", ttl=30 * TAG)


def klassen_bestimmen(ktx: Kontext, eltern: dict[str, set[str]], max_stufen: int = 40) -> dict[str, str]:
    """Taxon-QID → Tiergruppe. Nur eindeutige Zuordnungen (eine Gruppe)."""
    vorfahren: dict[str, set[str]] = {}
    offen = {q: set(ps) for q, ps in eltern.items()}
    gefunden: dict[str, set[str]] = {}
    for _ in range(max_stufen):
        fehlend = sorted({p for ps in offen.values() for p in ps if p not in vorfahren and p not in KLASSEN})
        for i in range(0, len(fehlend), 300):
            paket = fehlend[i : i + 300]
            for r in abfrage(ktx.http, "SELECT ?t ?p WHERE { VALUES ?t { "
                             + " ".join(f"wd:{x}" for x in paket) + " } ?t wdt:P171 ?p }", ttl=30 * TAG):
                vorfahren.setdefault(qid(r["t"]), set()).add(qid(r["p"]))
            for x in paket:
                vorfahren.setdefault(x, set())
        weiter = {}
        for q, ps in offen.items():
            treffer = {KLASSEN[p] for p in ps if p in KLASSEN}
            if treffer:
                gefunden[q] = treffer
                continue
            hoeher = {v for p in ps for v in vorfahren.get(p, ())}
            if hoeher:
                weiter[q] = hoeher
        offen = weiter
        if not offen:
            break
    return {q: next(iter(g)) for q, g in gefunden.items() if len(g) == 1}


def artikel_aus_einleitung(einleitung: str, label: str) -> str | None:
    """„Der Blauwal (Balaenoptera musculus) ist …“ → „der“. None bei Plural oder anderem Satzbau."""
    m = _ARTIKEL.match(einleitung.strip())
    if not m or swiss(m.group(2)) != swiss(label):
        return None
    return m.group(1).lower()


def einleitungen(ktx: Kontext, titel: list[str]) -> dict[str, str]:
    """Erster Absatz pro Artikel (20 Titel pro Request, Grenze der API für Einleitungen)."""
    ergebnis: dict[str, str] = {}
    for i in range(0, len(titel), 20):
        res = ktx.http.json(API_URL, params={
            "action": "query", "format": "json", "formatversion": "2", "prop": "extracts",
            "exintro": "1", "explaintext": "1", "exlimit": "20", "redirects": "1", "titles": "|".join(titel[i : i + 20]),
        }, ttl=30 * TAG)
        for p in res.get("query", {}).get("pages", []):
            ergebnis[p["title"]] = p.get("extract", "")
    return ergebnis


def _gekappt(fragen: list[Frage], gruppe: dict[str, str]) -> list[Frage]:
    """Bekannteste zuerst, höchstens MAX_PRO_KLASSE pro Tiergruppe."""
    zaehler: dict[str, int] = {}
    ergebnis = []
    for f in sorted(fragen, key=lambda f: -f.score):
        g = gruppe[f.quelle_id]
        if zaehler.get(g, 0) < MAX_PRO_KLASSE:
            zaehler[g] = zaehler.get(g, 0) + 1
            ergebnis.append(f)
    return ergebnis


def generiere(ktx: Kontext) -> dict[str, list[Frage]]:
    rows = bekannte_arten(ktx)
    # Startpunkt: die Art selbst; klassen_bestimmen holt von dort aus die Elterntaxa
    gruppe = klassen_bestimmen(ktx, {qid(r["item"]): {qid(r["item"])} for r in rows})
    arten = {qid(r["item"]): r for r in rows if qid(r["item"]) in gruppe}
    bekannt = sorted(ktx.filtern([_kandidat(r) for r in arten.values()], "tier", schwellen=SCHWELLEN_TIER),
                     key=lambda k: -(k.pageviews or 0))
    log.info("Tiere: %d Arten mit Tiergruppe, %d bekannt", len(arten), len(bekannt))
    texte = einleitungen(ktx, [k.titel for k in bekannt])

    # Tiere mit Artikel im Singular → tierklasse, die übrigen → welches_tier
    klasse_fragen, rest = [], []
    for k in bekannt:
        name = swiss(k.label)
        artikel = artikel_aus_einleitung(texte.get(k.titel, ""), k.label)
        g = gruppe[k.qid]
        if artikel:
            falsch = VERWECHSLUNG[g][:3]
            klasse_fragen.append(Frage(
                kategorie=ktx.kategorie, frage=f"Zu welcher Tiergruppe gehört {artikel} {name}?", richtig=g,
                falsch=falsch, schwierigkeit=2, quelle_typ="wikidata", quelle_url=artikel_url(k.titel),
                quelle_titel=k.titel, quelle_id=k.qid, template="tierklasse", score=k.pageviews or 0))
        else:
            rest.append(k)
    klasse_fragen = _gekappt(klasse_fragen, gruppe)
    verwendet = {f.quelle_id for f in klasse_fragen}

    # „Welches dieser Tiere ist ein …?“: Antwort und Distraktoren aus Tieren, die nicht schon in
    # `tierklasse` vorkommen; Distraktoren aus den verwechselbaren Gruppen
    pool = [k for k in bekannt if k.qid not in verwendet]
    nach_gruppe: dict[str, list[Kandidat]] = {}
    for k in pool:
        nach_gruppe.setdefault(gruppe[k.qid], []).append(k)
    welche = []
    for k in pool:
        g = gruppe[k.qid]
        rng = ktx.rng("welches_tier", k.qid)
        andere = [x for vg in VERWECHSLUNG[g][:3] for x in nach_gruppe.get(vg, [])[:8]]
        if len(andere) < 3:
            continue
        falsch = [swiss(x.label) for x in rng.sample(andere, 3)]
        welche.append(Frage(
            kategorie=ktx.kategorie, frage=f"Welches dieser Tiere ist {EINZAHL[g]}?", richtig=swiss(k.label),
            falsch=falsch, schwierigkeit=2, quelle_typ="wikidata", quelle_url=artikel_url(k.titel),
            quelle_titel=k.titel, quelle_id=k.qid, template="welches_tier", score=k.pageviews or 0))
    welche = _gekappt(welche, gruppe)

    gruppen = {"tierklasse": klasse_fragen, "welches_tier": welche}
    for name, fragen in gruppen.items():
        del fragen[MAX_PRO_TEMPLATE[name]:]
        stufen_nach_rang(fragen)
    return gruppen
