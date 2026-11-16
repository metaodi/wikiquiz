"""Wikidata-Templates für die Kategorie Tiere & Natur.

Templates (jedes Tier kommt nur in einem davon vor, sonst verrieten sich die Fragen):
- tierklasse: „Zu welcher Tiergruppe gehört der Blauwal?“ → Säugetiere (Fische, Vögel, Reptilien)
- welches_tier: „Welches dieser Tiere ist ein Säugetier?“ → Pottwal (Walhai, Weisser Hai, Kaiserpinguin)

Gefragt werden vor allem Tiere, bei denen man sich leicht irrt (UEBERRASCHEND: Wale, Pinguine,
Seepferdchen, Blindschleiche …), mit der naheliegenden Verwechslung als Distraktor.

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
# Tiergruppen, bei denen man sich leicht irrt: Taxon → naheliegende falsche Tiergruppe.
# Solche Tiere werden bevorzugt gefragt; „Zu welcher Tiergruppe gehört der Löwe?“ ist zu einfach.
UEBERRASCHEND = {
    "Q160": "Fische",          # Wale
    "Q25431": "Fische",        # Seekühe
    "Q30263": "Fische",        # Robben
    "Q971343": "Vögel",        # Fledermäuse
    "Q21790": "Reptilien",     # Kloakentiere (Schnabeltier legt Eier)
    "Q9147": "Säugetiere",     # Pinguine
    "Q840849": "Säugetiere",   # Laufvögel (Strauss, Emu, Kiwi)
    "Q7372": "Säugetiere",     # Haie
    "Q6495741": "Säugetiere",  # Rochen
    "Q128685": "Reptilien",    # Aalartige
    "Q74363": "Reptilien",     # Seepferdchen
    "Q183686": "Vögel",        # Fliegende Fische
    "Q168422": "Amphibien",    # Lungenfische
    "Q191059": "Amphibien",    # Schleichen (Blindschleiche)
    "Q53663": "Reptilien",     # Schwanzlurche (Salamander, Molche)
    "Q4758": "Reptilien",      # Schleichenlurche
    "Q25363": "Amphibien",     # Krokodile
    "Q223044": "Amphibien",    # Schildkröten
}
# Höchstens so viele Tiere pro überraschendem Taxon (sonst zehn Wale) und gewöhnliche Tiere pro Gruppe
MAX_PRO_TAXON = 3
MAX_GEWOEHNLICH_PRO_KLASSE = 1

EINZAHL = {"Säugetiere": "ein Säugetier", "Vögel": "ein Vogel", "Reptilien": "ein Reptil",
           "Amphibien": "eine Amphibie", "Fische": "ein Fisch", "Insekten": "ein Insekt",
           "Spinnentiere": "ein Spinnentier"}

MAX_PRO_TEMPLATE = {"tierklasse": 25, "welches_tier": 15}
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


def klassen_bestimmen(ktx: Kontext, eltern: dict[str, set[str]], max_stufen: int = 40
                      ) -> tuple[dict[str, str], dict[str, set[str]]]:
    """Taxon-QID → Tiergruppe (nur eindeutige Zuordnungen) und Taxon-QID → alle gefundenen Vorfahren."""
    vorfahren: dict[str, set[str]] = {}
    offen = {q: set(ps) for q, ps in eltern.items()}
    alle: dict[str, set[str]] = {q: set(ps) for q, ps in eltern.items()}
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
                alle[q] |= hoeher
        offen = weiter
        if not offen:
            break
    return {q: next(iter(g)) for q, g in gefunden.items() if len(g) == 1}, alle


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


def generiere(ktx: Kontext) -> dict[str, list[Frage]]:
    rows = bekannte_arten(ktx)
    # Startpunkt: die Art selbst; klassen_bestimmen holt von dort aus die Elterntaxa
    gruppe, vorfahren = klassen_bestimmen(ktx, {qid(r["item"]): {qid(r["item"])} for r in rows})
    arten = {qid(r["item"]): r for r in rows if qid(r["item"]) in gruppe}
    bekannt = sorted(ktx.filtern([_kandidat(r) for r in arten.values()], "tier", schwellen=SCHWELLEN_TIER),
                     key=lambda k: -(k.pageviews or 0))
    log.info("Tiere: %d Arten mit Tiergruppe, %d bekannt", len(arten), len(bekannt))

    # Überraschende Tiere (Wal, Pinguin, Seepferdchen …), höchstens MAX_PRO_TAXON pro Taxon
    taxon_von: dict[str, str] = {}
    pro_taxon: dict[str, int] = {}
    for k in bekannt:
        taxa = sorted(vorfahren.get(k.qid, set()) & UEBERRASCHEND.keys())
        if len(taxa) == 1 and UEBERRASCHEND[taxa[0]] != gruppe[k.qid]:
            if pro_taxon.get(taxa[0], 0) < MAX_PRO_TAXON:
                pro_taxon[taxa[0]] = pro_taxon.get(taxa[0], 0) + 1
                taxon_von[k.qid] = taxa[0]
    ueberraschend = [k for k in bekannt if k.qid in taxon_von]
    texte = einleitungen(ktx, [k.titel for k in ueberraschend] + [k.titel for k in bekannt[:60]])

    def verwechslung(k: Kandidat) -> list[str]:
        """Naheliegende falsche Gruppe zuerst, dann zwei weitere verwechselbare."""
        g = gruppe[k.qid]
        erste = UEBERRASCHEND.get(taxon_von.get(k.qid, ""))
        rest = [x for x in VERWECHSLUNG[g] if x != erste]
        rng = ktx.rng("verwechslung", k.qid)
        return [erste, *rng.sample(rest, 2)] if erste else rng.sample(VERWECHSLUNG[g], 3)

    def klassenfrage(k: Kandidat, artikel: str, score: float) -> Frage:
        return Frage(
            kategorie=ktx.kategorie, frage=f"Zu welcher Tiergruppe gehört {artikel} {swiss(k.label)}?",
            richtig=gruppe[k.qid], falsch=verwechslung(k), schwierigkeit=2, quelle_typ="wikidata",
            quelle_url=artikel_url(k.titel), quelle_titel=k.titel, quelle_id=k.qid, template="tierklasse",
            score=score)

    # Überraschende Tiere abwechselnd auf beide Templates verteilen (jedes Tier nur einmal);
    # ohne Artikel im Singular nur „Welches dieser Tiere …?“
    klasse_fragen: list[Frage] = []
    welche_antworten: list[Kandidat] = []
    for i, k in enumerate(ueberraschend):
        artikel = artikel_aus_einleitung(texte.get(k.titel, ""), k.label)
        if artikel and i % 2 == 0:
            klasse_fragen.append(klassenfrage(k, artikel, 1_000_000 + (k.pageviews or 0)))
        else:
            welche_antworten.append(k)
    # Wenige gewöhnliche Tiere dazu (leichte Fragen), höchstens eines pro Gruppe
    gewoehnlich: dict[str, int] = {}
    for k in bekannt[:60]:
        if k.qid in taxon_von or gewoehnlich.get(gruppe[k.qid], 0) >= MAX_GEWOEHNLICH_PRO_KLASSE:
            continue
        artikel = artikel_aus_einleitung(texte.get(k.titel, ""), k.label)
        if artikel:
            gewoehnlich[gruppe[k.qid]] = gewoehnlich.get(gruppe[k.qid], 0) + 1
            klasse_fragen.append(klassenfrage(k, artikel, k.pageviews or 0))

    # „Welches dieser Tiere ist ein Säugetier?“ → Blauwal; Distraktoren aus der Gruppe, mit der man das
    # Tier verwechselt (Walhai, Weisser Hai …), ergänzt durch eine weitere verwechselbare Gruppe
    # Fangfrage-Tiere der verwechselten Gruppe zuerst: Zum Walhai (Fisch) passen Wale und Robben als
    # Distraktoren, nicht Wolf oder Giraffe
    nach_gruppe: dict[str, list[Kandidat]] = {}
    for k in [*ueberraschend, *(k for k in bekannt if k.qid not in taxon_von)]:
        nach_gruppe.setdefault(gruppe[k.qid], []).append(k)
    welche = []
    for k in welche_antworten:
        g, erste = gruppe[k.qid], UEBERRASCHEND[taxon_von[k.qid]]
        rng = ktx.rng("welches_tier", k.qid)
        andere = [x for x in nach_gruppe.get(erste, []) if x.qid != k.qid]
        fang = [x for x in andere if x.qid in taxon_von][:6]
        andere = fang if len(fang) >= 2 else andere[:10]
        if len(andere) < 2:
            continue
        falsch = [swiss(x.label) for x in rng.sample(andere, 2)]
        weitere = [x for vg in VERWECHSLUNG[g] if vg != erste for x in nach_gruppe.get(vg, [])[:5]]
        if not weitere:
            continue
        falsch.append(swiss(rng.choice(weitere).label))
        welche.append(Frage(
            kategorie=ktx.kategorie, frage=f"Welches dieser Tiere ist {EINZAHL[g]}?", richtig=swiss(k.label),
            falsch=falsch, schwierigkeit=2, quelle_typ="wikidata", quelle_url=artikel_url(k.titel),
            quelle_titel=k.titel, quelle_id=k.qid, template="welches_tier", score=k.pageviews or 0))

    gruppen = {"tierklasse": sorted(klasse_fragen, key=lambda f: -f.score),
               "welches_tier": sorted(welche, key=lambda f: -f.score)}
    for name, fragen in gruppen.items():
        del fragen[MAX_PRO_TEMPLATE[name]:]
        stufen_nach_rang(fragen)
    return gruppen
