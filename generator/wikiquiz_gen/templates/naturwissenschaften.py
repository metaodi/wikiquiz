"""Wikidata-Templates für die Kategorie Naturwissenschaften & Technik.

Templates:
- element:   „Welches chemische Element hat das Symbol Fe?“ bzw. „Welches chemische Symbol hat Gold?“
- einheit:   „Welche physikalische Grösse wird in Watt angegeben?“ bzw. „In welcher Einheit wird … angegeben?“
- nobelpreis: „In welchem Fachgebiet erhielt Max Planck den Nobelpreis?“
- entdeckung: „Wer entdeckte das Elektron?“

Bewusst nicht verwendet: das allgemeine Wikidata-Merkmal „Entdecker oder Erfinder“ (P61) für Erfindungen
und chemische Elemente. Dort stehen viele umstrittene oder falsche Angaben (z. B. Auto → Ferdinand Verbiest,
Kohlenstoff → Lavoisier). Erfindungen deckt die LLM-Pipeline mit unabhängiger Prüfung ab.
"""
from __future__ import annotations

import logging

from ..models import Frage, swiss
from ..popularity import Kandidat
from ..sparql import abfrage, artikel_url, qid, titel_aus_url
from .base import Kontext, naechste_nach_bekanntheit, stufen_nach_rang

log = logging.getLogger(__name__)

CHEMISCHES_ELEMENT = "Q11344"

# Einheit → Hauptgrösse. Wikidata führt pro Einheit Dutzende Grössen (Kelvin u. a. „Taupunkt“),
# darum kuratiert; jedes Paar wird gegen P111 („gemessene physikalische Grösse“) geprüft.
EINHEITEN = {
    "Q11573": "Q36253",    # Meter → Länge
    "Q11574": "Q2199864",  # Sekunde → Dauer
    "Q11570": "Q11423",    # Kilogramm → Masse
    "Q11579": "Q264647",   # Kelvin → thermodynamische Temperatur
    "Q25272": "Q29996",    # Ampere → elektrische Stromstärke
    "Q41509": "Q104946",   # Mol → Stoffmenge
    "Q83216": "Q104831",   # Candela → Lichtstärke
    "Q12438": "Q11402",    # Newton → Kraft
    "Q25269": "Q11379",    # Joule → Energie
    "Q25236": "Q25342",    # Watt → Leistung
    "Q25250": "Q25428",    # Volt → elektrische Spannung
    "Q47083": "Q25358",    # Ohm → elektrischer Widerstand
    "Q39369": "Q11652",    # Hertz → Frequenz
    "Q44395": "Q39552",    # Pascal → Druck
    "Q131255": "Q164399",  # Farad → elektrische Kapazität
    "Q26162": "Q105298",   # Tesla → magnetische Flussdichte
    "Q179836": "Q194411",  # Lux → Beleuchtungsstärke
    "Q484092": "Q107780",  # Lumen → Lichtstrom
}
# Kürzere, geläufigere Bezeichnungen für die Anzeige
GROESSE_ANZEIGE = {"Dauer": "Zeit", "thermodynamische Temperatur": "Temperatur"}

NOBELPREISE = {
    "Q38104": "Physik",
    "Q44585": "Chemie",
    "Q80061": "Medizin",  # Physiologie oder Medizin
    "Q37922": "Literatur",
    "Q35637": "Frieden",
    "Q47170": "Wirtschaftswissenschaften",
}
NOBEL_NATURWISS = ("Q38104", "Q44585", "Q80061")

# Bekannte Entdeckungen mit eindeutigem Entdecker (Wikidata P61, genau eine Person)
ENTDECKUNGEN = [
    "Q2225", "Q2294", "Q2348", "Q3229",        # Elektron, Proton, Neutron, Positron
    "Q324", "Q339", "Q596",                    # Uranus, Pluto, Ceres
    "Q3123", "Q3143", "Q3134", "Q3169",        # Io, Europa, Ganymed, Kallisto
    "Q12198",                                  # Penicillin
]

JUPITERMONDE = ("Q3123", "Q3143", "Q3134", "Q3169")
HIMMELSKOERPER = ("Q324", "Q339", "Q596", *JUPITERMONDE)

MAX_PRO_TEMPLATE = {"element": 30, "einheit": 18, "nobelpreis": 30, "entdeckung": 12}


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


# ---------------------------------------------------------------------------
def element(ktx: Kontext) -> list[Frage]:
    """Pro Element genau eine Richtung (Symbol → Element oder Element → Symbol), sonst verrät
    die eine Frage die andere im selben Spiel."""
    rows = abfrage(ktx.http, f"""
SELECT ?item ?label ?article ?sl ?sym ?z WHERE {{
  ?item wdt:P31 wd:{CHEMISCHES_ELEMENT}; wdt:P246 ?sym; wdt:P1086 ?z.
  {_artikel_teil()}
}}""")
    symbole = {qid(r["item"]): r["sym"] for r in rows}
    bekannt = ktx.filtern([_kandidat(r) for r in rows], "element")
    # Distraktoren aus allen gängigen Elementen bis Plutonium (Ordnungszahl ≤ 94), nicht nur den
    # bekanntesten: So passen sie zum Anfangsbuchstaben (Cu → Cobalt, Cadmium statt Aluminium, Uran).
    # Superschwere künstliche Elemente (Flerovium, Oganesson …) wären zu offensichtlich falsch.
    distraktoren = [(swiss(r["label"]), r["sym"], int(r["sl"])) for r in rows
                    if int(r["sl"]) >= 100 and int(float(r["z"])) <= 94]
    fragen = []
    for k in bekannt:
        sym = symbole[k.qid]
        name = swiss(k.label)
        rng = ktx.rng("element", k.qid)
        andere = [(n, s, sl) for n, s, sl in distraktoren if s != sym]
        if rng.random() < 0.5:
            # Symbol → Element: Elemente, deren Symbol oder Name mit demselben Buchstaben beginnt
            aehnlich = [n for n, s, _ in sorted(andere, key=lambda e: -e[2]) if s[0] == sym[0] or n[0] == sym[0]][:6]
            rest = [n for n, s, sl in sorted(andere, key=lambda e: -e[2]) if n not in aehnlich][:20]
            frage, richtig = f"Welches chemische Element hat das Symbol {sym}?", name
        else:
            # Element → Symbol: echte Symbole mit dem Anfangsbuchstaben von Name oder Symbol
            anfang = {name[0].upper(), sym[0]}
            aehnlich = [s for n, s, _ in sorted(andere, key=lambda e: -e[2]) if s[0] in anfang][:6]
            rest = [s for n, s, sl in sorted(andere, key=lambda e: -e[2]) if s not in aehnlich][:20]
            frage, richtig = f"Welches chemische Symbol hat das Element {name}?", sym
        falsch = rng.sample(aehnlich, min(3, len(aehnlich)))
        if len(falsch) < 3:
            falsch += rng.sample(rest, 3 - len(falsch))
        fragen.append(_frage(ktx, k, frage, richtig, falsch, "element", k.pageviews or 0))
    return fragen


def einheit(ktx: Kontext) -> list[Frage]:
    werte = " ".join(f"(wd:{u} wd:{g})" for u, g in EINHEITEN.items())
    rows = abfrage(ktx.http, f"""
SELECT ?item ?label ?article ?sl ?groesse ?gl WHERE {{
  VALUES (?item ?groesse) {{ {werte} }}
  ?item wdt:P111 ?groesse.
  ?groesse rdfs:label ?gl. FILTER(LANG(?gl) = "de")
  {_artikel_teil()}
}}""")
    pruefbar = {qid(r["item"]) for r in rows}
    for u in EINHEITEN:
        if u not in pruefbar:
            ktx.protokoll.verwerfen(ktx.kategorie, "template:einheit", "groesse nicht in P111 oder kein artikel",
                                    {"qid": u})
    groesse = {qid(r["item"]): GROESSE_ANZEIGE.get(r["gl"], r["gl"]) for r in rows}
    einheiten = ktx.filtern([_kandidat(r) for r in rows], "einheit")
    namen = {k.qid: k.label for k in einheiten}
    fragen = []
    for k in einheiten:
        rng = ktx.rng("einheit", k.qid)
        g = groesse[k.qid]
        if rng.random() < 0.5:
            andere = sorted({groesse[q] for q in namen if q != k.qid} - {g})
            falsch = rng.sample(andere, 3)
            frage = f"Welche physikalische Grösse wird in der Einheit {namen[k.qid]} angegeben?"
            richtig = g
        else:
            andere = sorted({namen[q] for q in namen if q != k.qid and groesse[q] != g})
            falsch = rng.sample(andere, 3)
            # Maskulin: „der elektrische Widerstand“, „der Druck“, „der Lichtstrom“; sonst feminin
            artikel = "der" if g.startswith("elektrischer") or g in ("Druck", "Lichtstrom") else "die"
            frage = f"In welcher Einheit wird {artikel} {g} angegeben?"
            richtig = namen[k.qid]
        fragen.append(_frage(ktx, k, frage, richtig, falsch, "einheit", k.sitelinks))
    return fragen


def nobelpreis(ktx: Kontext) -> list[Frage]:
    """Nur Personen mit genau einem Nobelpreis (Marie Curie u. a. ausgeschlossen)."""
    preise = " ".join(f"wd:{p}" for p in NOBELPREISE)
    rows = abfrage(ktx.http, f"""
SELECT ?item ?label ?article ?sl (GROUP_CONCAT(DISTINCT STRAFTER(STR(?preis), "entity/")) AS ?preise) WHERE {{
  VALUES ?preis {{ {preise} }}
  ?item wdt:P166 ?preis; wdt:P31 wd:Q5.
  {_artikel_teil()}
  FILTER(?sl >= {ktx.schwellen.min_sitelinks})
}} GROUP BY ?item ?label ?article ?sl
HAVING (COUNT(DISTINCT ?preis) = 1)
ORDER BY DESC(?sl) LIMIT {ktx.max_kandidaten}""")
    preis = {qid(r["item"]): r["preise"] for r in rows if r["preise"] in NOBEL_NATURWISS}
    personen = ktx.filtern([_kandidat(r) for r in rows if qid(r["item"]) in preis], "nobelpreis")
    fragen = []
    for k in personen:
        rng = ktx.rng("nobelpreis", k.qid)
        richtig = NOBELPREISE[preis[k.qid]]
        andere = [NOBELPREISE[p] for p in NOBEL_NATURWISS if p != preis[k.qid]]
        falsch = andere + [rng.choice(["Literatur", "Frieden"])]
        frage = f"In welchem Fachgebiet erhielt {swiss(k.label)} den Nobelpreis?"
        fragen.append(_frage(ktx, k, frage, richtig, falsch, "nobelpreis", k.pageviews or 0))
    return fragen


def entdeckung(ktx: Kontext) -> list[Frage]:
    werte = " ".join(f"wd:{q}" for q in ENTDECKUNGEN)
    rows = abfrage(ktx.http, f"""
SELECT ?item ?label ?article ?sl ?person ?pl ?geboren (COUNT(DISTINCT ?p2) AS ?n) WHERE {{
  VALUES ?item {{ {werte} }}
  ?item wdt:P61 ?person; wdt:P61 ?p2. ?person wdt:P31 wd:Q5.
  ?person rdfs:label ?pl. FILTER(LANG(?pl) = "de")
  OPTIONAL {{ ?person wdt:P569 ?geboren }}
  {_artikel_teil()}
}} GROUP BY ?item ?label ?article ?sl ?person ?pl ?geboren""")
    eindeutig = [r for r in rows if r["n"] == "1"]
    for r in rows:
        if r["n"] != "1":
            ktx.protokoll.verwerfen(ktx.kategorie, "template:entdeckung", "mehrere entdecker",
                                    {"qid": qid(r["item"]), "label": r["label"]})
    themen = {k.qid: k for k in ktx.filtern([_kandidat(r) for r in eindeutig], "entdeckung")}
    entdecker = {qid(r["item"]): (swiss(r["pl"]), int(r.get("geboren", "0000")[:4] or 0)) for r in eindeutig}
    # Distraktoren: bekannte Fachleute desselben Gebiets mit ähnlichem Geburtsjahr
    # (Astronomen für Himmelskörper, Physiker für Teilchen, Ärzte/Biologen für Penicillin)
    def fachleute(berufe: list[str]) -> list[tuple[str, int]]:
        werte = " ".join(f"wd:{b}" for b in berufe)
        rows = abfrage(ktx.http, f"""
SELECT DISTINCT ?pl ?jahr WHERE {{
  VALUES ?beruf {{ {werte} }}
  ?p wdt:P106 ?beruf; wdt:P569 ?geboren; wikibase:sitelinks ?sl. FILTER(?sl >= 100)
  FILTER NOT EXISTS {{ ?p wdt:P106 wd:Q155647 }}  # keine Astrologen (Nostradamus)
  ?p rdfs:label ?pl. FILTER(LANG(?pl) = "de") BIND(YEAR(?geboren) AS ?jahr)
}}""")
        return [(swiss(r["pl"]), int(r["jahr"])) for r in rows if r.get("jahr")]

    gebiete = {"astronomie": fachleute(["Q11063"]), "physik": fachleute(["Q169470"]),
               "medizin": fachleute(["Q39631", "Q864503"])}
    fragen = []
    for q, k in themen.items():
        name, jahr = entdecker[q]
        rng = ktx.rng("entdeckung", q)
        gebiet = "astronomie" if q in HIMMELSKOERPER else "medizin" if q == "Q12198" else "physik"
        nahe = sorted({p for p in gebiete[gebiet] if p[0] != name}, key=lambda p: abs(p[1] - jahr))[:5]
        falsch = rng.sample([p[0] for p in nahe], 3)
        if q in JUPITERMONDE:
            frage = f"Wer entdeckte den Jupitermond {swiss(k.label)}?"
        elif q in HIMMELSKOERPER:
            frage = f"Wer entdeckte {swiss(k.label)}?"  # Himmelskörper ohne Artikel
        else:
            frage = f"Wer entdeckte das {swiss(k.label)}?"  # Elektron, Proton, Neutron, Positron, Penicillin
        fragen.append(_frage(ktx, k, frage, name, falsch, "entdeckung", k.pageviews or 0))
    return fragen


def generiere(ktx: Kontext) -> dict[str, list[Frage]]:
    gruppen = {
        "element": element(ktx),
        "einheit": einheit(ktx),
        "nobelpreis": nobelpreis(ktx),
        "entdeckung": entdeckung(ktx),
    }
    for name, fragen in gruppen.items():
        fragen.sort(key=lambda f: -f.score)
        del fragen[MAX_PRO_TEMPLATE[name]:]
        stufen_nach_rang(fragen)
    return gruppen
