"""Quellen für Wikipedia-Artikel pro Quizkategorie.

1. Thematische Kategorien der deutschsprachigen Wikipedia (mit begrenzter Suchtiefe)
2. „Exzellente“ und „Lesenswerte“ Artikel, über ihre Wikipedia-Kategorien per Stichwort zugeordnet

Danach greift der gemeinsame Bekanntheitsfilter (Sitelinks, Seitenaufrufe, Länge …).
"""
from __future__ import annotations

import re

# (Kategorie ohne Präfix, Suchtiefe in Unterkategorien)
STARTKATEGORIEN: dict[str, list[tuple[str, int]]] = {
    "naturwissenschaften": [
        ("Chemisches Element", 0),
        ("Planet des Sonnensystems", 0),
        ("Nobelpreisträger für Physik", 0),
        ("Nobelpreisträger für Chemie", 0),
        ("Nobelpreisträger für Physiologie oder Medizin", 0),
        ("Erfindung", 1),
        ("Raumfahrt", 1),
        ("Krankheit", 1),
    ],
    "kunst": [
        ("Maler der Renaissance", 0),
        ("Maler", 1),
        ("Gemälde", 1),
        ("Komponist (Klassik)", 0),
        ("Komponist (Barock)", 0),
        ("Komponist (Romantik)", 0),
        ("Oper", 1),
        ("Musical", 1),
        ("Roman, Epik", 0),
        ("Drama", 0),
        ("Musikinstrument", 1),
        ("Kunstmuseum", 1),
    ],
    "geschichte": [
        ("Kaiser (Rom)", 0),
        ("Pharao", 1),
        ("Präsident der Vereinigten Staaten", 0),
        ("Bundeskanzler (Deutschland)", 0),
        ("Erster Weltkrieg", 1),
        ("Zweiter Weltkrieg", 1),
        ("Schlacht", 1),
        ("Revolution", 1),
        ("Herrscher", 1),
        # Mehr Epochen, damit nicht NS-Zeit und Weltkriege überwiegen (siehe themen.py)
        ("Altes Ägypten", 1),
        ("Römisches Reich", 1),
        ("Mittelalter", 1),
        ("Kreuzzug", 0),
        ("Frühe Neuzeit", 1),
        ("Person der Reformation", 0),
        ("Entdecker", 0),
        ("Französische Revolution", 1),
        ("Kalter Krieg", 0),
        ("Schweizerische Geschichte", 1),
        ("Person (Schweizer Geschichte)", 0),
        # Gesellschaft: Religion, Bräuche, Feiertage, Philosophie
        ("Feiertag", 0),
        ("Weltreligion", 0),
        ("Brauch", 1),
        ("Philosoph (Antike)", 0),
        ("Philosoph der Aufklärung", 0),
    ],
    "sport": [
        ("Olympische Sportart", 0),
        ("Olympische Spiele", 1),
        ("Sportart", 1),
        ("Fußballspieler (Deutschland)", 1),
        ("Tennisspieler (Schweiz)", 0),
        ("Popsänger", 0),
        ("Rockband", 0),
        ("Fernsehserie (Vereinigte Staaten)", 0),
        ("Film", 1),
        ("Computerspiel", 1),
        ("Brettspiel", 0),
        ("Kartenspiel", 0),
    ],
    "geografie": [
        ("Hauptstadt in Europa", 0),
        ("Fluss", 1),
        ("Gebirge", 1),
        ("Insel", 1),
        ("See", 1),
        ("Sprache", 0),
    ],
    "essen": [
        ("Lebensmittel", 1),
        ("Getränk", 1),
        ("Nationale Küche", 1),
        ("Obst", 1),
        ("Gemüse", 1),
        ("Gewürz", 0),
        ("Käsesorte", 0),
        ("Spirituose", 1),
        ("Biersorte", 0),
        ("Backware", 1),
    ],
    "natur": [
        ("Haustier", 1),
        ("Nutztier", 1),
        ("Säugetiere", 0),
        ("Vögel", 0),
        ("Reptilien", 0),
        ("Hunderasse", 0),
        ("Nutzpflanze", 1),
        ("Baum", 0),
    ],
    # Themenkategorien (config.THEMENKATEGORIEN): kein Kategorie-Abgleich
    "schweiz": [
        ("Bundesrat (Schweiz)", 0),
        ("Kanton (Schweiz)", 0),
        ("Hauptort eines Schweizer Kantons", 0),
        ("Geschichte der Schweiz", 1),
        ("Politik (Schweiz)", 1),
        ("Alpenpass", 0),
        ("See in der Schweiz", 1),
        ("Fluss in der Schweiz", 1),
        ("Berg in den Alpen", 0),
        ("Schweizer Küche", 1),
        ("Brauchtum (Schweiz)", 1),
        ("Unternehmen (Schweiz)", 0),
        ("Erfindung (Schweiz)", 0),
    ],
    "starwars": [
        ("Star Wars", 2),
    ],
}

QUALITAETSKATEGORIEN = ["Wikipedia:Exzellent", "Wikipedia:Lesenswert"]

# Themenkategorien: Exzellente/Lesenswerte Artikel, deren Wikipedia-Kategorien eines dieser
# Stichworte enthalten (Gross-/Kleinschreibung egal). Unabhängig von `zuordnen`, weil ein
# Artikel thematisch und fachlich zugleich passt (Gotthardpass: Schweiz und Geografie).
THEMEN_STICHWORTE: dict[str, list[str]] = {
    "schweiz": ["(schweiz)", "in der schweiz", "schweizer"],
    "starwars": ["star wars", "star-wars"],
}


def zum_thema(kategorien: list[str], thema: str) -> bool:
    """Gehört ein Artikel laut seinen Wikipedia-Kategorien zur Themenkategorie `thema`?"""
    namen = [k.lower().removeprefix("kategorie:") for k in kategorien]
    return any(w in n for n in namen for w in THEMEN_STICHWORTE.get(thema, []))


# Stichworte in den (nicht versteckten) Kategorien eines Artikels → Quizkategorie.
# Ein Stichwort zählt nur am Wortanfang: „Dichter (Deutsch)“ ja, „Verdichter“ oder
# „Kirchenlieddichter“ nein. Gewicht 2 für eindeutige Stichworte; pro Kategoriename zählt
# das stärkste Stichwort. Zuordnung nur bei eindeutigem Höchstwert (mind. 2 Punkte).
# „Literatur (…)“ zählt bewusst nicht: Wikipedia ordnet so alle ein, die je etwas
# veröffentlicht haben, auch Astronomen oder Politiker.
STICHWORTE: dict[str, dict[str, int]] = {
    "naturwissenschaften": {
        "physik": 2, "astrophysik": 2, "kernphysik": 2, "chemi": 2, "biochemi": 2, "biolog": 1,
        "astronom": 2, "kosmolog": 2, "mathemat": 2, "geometrie": 2, "besondere zahl": 2,
        "zahlentheorie": 2, "medizin": 1, "krankheit": 2, "erfind": 2, "informatik": 2,
        "chemisches element": 2, "planet": 2, "galaxie": 2, "geolog": 1, "anatomie": 2,
        "genetik": 2, "raumfahrt": 2, "technik": 1, "verbrennungsmotor": 2, "maschinenbau": 2,
        # Flugzeugtypen (Boeing 747, F-14) gehören zur Technik, auch militärische
        "erstflug": 2, "flugzeug": 2, "luftfahrzeug": 2,
        "nobelpreisträger für physik": 2, "nobelpreisträger für chemie": 2,
        "nobelpreisträger für physiologie": 2, "naturwissenschaftler": 2, "elektr": 1,
    },
    "kunst": {
        "maler": 2, "malerei": 2, "gemälde": 2, "komponist": 2, "oper": 2, "opernkomponist": 2,
        "roman": 2, "novelle": 2, "erzählung": 1, "literarisches werk": 2, "schriftsteller": 1,
        "dichter": 2, "lyrik": 2, "drama": 1, "bildhauer": 2, "skulptur": 2, "architekt": 1,
        "theater": 1, "ballett": 2, "klassische musik": 2, "musikinstrument": 2, "museum": 1,
    },
    "geschichte": {
        "geschichte": 1, "krieg": 2, "weltkrieg": 2, "schlacht": 2, "herrscher": 2, "kaiser": 2,
        "könig": 1, "pharao": 2, "dynastie": 2, "revolution": 2, "antike": 1, "mittelalter": 1,
        "imperium": 2, "präsident": 1, "bundeskanzler": 2, "archäolog": 1, "militär": 1,
        "politiker": 2, "feldherr": 2, "konsul": 2, "reformat": 2, "widerstandskämpfer": 2,
        "nationalsozialismus": 2, "holocaust": 2, "opfer des": 2, "nsdap": 2, "häftling": 2,
        "hingerichtete person": 2, "friedensnobelpreisträger": 2, "historisches dokument": 2,
        "rechtsquelle": 2, "antike rechtsquelle": 2,
        # Gesellschaft
        "feiertag": 2, "religion": 1, "brauch": 2, "philosoph": 2, "theolog": 1, "pädagog": 2,
        "anthroposoph": 2,
    },
    "sport": {
        "sport": 2, "fußball": 2, "olympi": 2, "tennis": 2, "film": 2, "fernseh": 2,
        "serie": 1, "schauspieler": 2, "popmusik": 2, "rockmusik": 2, "rockband": 2, "sänger": 1,
        "computerspiel": 2, "comic": 2, "weltmeister": 2, "brettspiel": 2, "kartenspiel": 2, "spiel": 1,
    },
    "geografie": {
        "fluss": 2, "gebirge": 2, "berg in": 2, "insel": 2, "see in": 2, "hauptstadt": 2,
        "geographie": 2, "geografie": 2, "nationalpark": 2, "wüste": 2, "landschaft": 1,
        "staat in": 2, "ort in": 1, "stadt in": 1, "sprache": 1,
    },
    "essen": {
        "lebensmittel": 2, "getränk": 2, "speise": 2, "küche": 2, "obst": 2, "gemüse": 2, "gewürz": 2,
        "käse": 2, "bier": 2, "wein": 1, "spirituose": 2, "backware": 2, "süßware": 2, "kochen": 2,
    },
    "natur": {
        "säugetier": 2, "haustier": 2, "nutztier": 2, "hunderasse": 2, "vögel": 2, "reptil": 2,
        "insekt": 2, "fische": 1, "tierart": 2, "pflanze": 1, "nutzpflanze": 2, "baum": 1,
    },
}

# Berufe aus Wikidata (P106) → (Quizkategorie, Gewicht). Für Personen oft aussagekräftiger als
# Wikipedia-Kategorien: Kepler ist Astronom und Mathematiker, auch wenn er Bücher schrieb.
# „Schriftsteller“ zählt nur schwach, weil es bei vielen Personen nebenbei vermerkt ist.
# Nicht aufgeführt (neutral): Journalist, Aktivist, Hochschullehrer, Sänger, Musiker u. ä.
BERUFE: dict[str, tuple[str, int]] = {
    # Kunst, Musik & Literatur
    "Q36180": ("kunst", 1),    # Schriftsteller
    "Q49757": ("kunst", 2),    # Dichter
    "Q6625963": ("kunst", 2),  # Romancier
    "Q214917": ("kunst", 2),   # Dramatiker
    "Q36834": ("kunst", 2),    # Komponist
    "Q1028181": ("kunst", 2),  # Maler
    "Q1281618": ("kunst", 2),  # Bildhauer
    "Q3391743": ("kunst", 2),  # bildender Künstler
    "Q483501": ("kunst", 1),   # Künstler
    "Q42973": ("kunst", 1),    # Architekt
    "Q8178443": ("kunst", 2),  # Librettist
    "Q486748": ("kunst", 2),   # Pianist
    "Q158852": ("kunst", 2),   # Dirigent
    "Q11774202": ("kunst", 1), # Essayist
    # Sport & Unterhaltung
    "Q33999": ("sport", 2),    # Schauspieler
    "Q2259451": ("sport", 1),  # Theaterschauspieler
    "Q2526255": ("sport", 2),  # Filmregisseur
    "Q28389": ("sport", 1),    # Drehbuchautor
    "Q2066131": ("sport", 2),  # Sportler
    "Q937857": ("sport", 2),   # Fussballspieler
    "Q10833314": ("sport", 2), # Tennisspieler
    "Q378622": ("sport", 2),   # Rennfahrer
    # Naturwissenschaften & Technik
    "Q169470": ("naturwissenschaften", 2),  # Physiker
    "Q593644": ("naturwissenschaften", 2),  # Chemiker
    "Q170790": ("naturwissenschaften", 2),  # Mathematiker
    "Q11063": ("naturwissenschaften", 2),   # Astronom
    "Q864503": ("naturwissenschaften", 2),  # Biologe
    "Q39631": ("naturwissenschaften", 1),   # Arzt
    "Q205375": ("naturwissenschaften", 2),  # Erfinder
    "Q81096": ("naturwissenschaften", 2),   # Ingenieur
    "Q82594": ("naturwissenschaften", 2),   # Informatiker
    "Q901": ("naturwissenschaften", 1),     # Wissenschaftler
    # Geschichte
    "Q82955": ("geschichte", 2),   # Politiker
    "Q189290": ("geschichte", 2),  # Offizier
    "Q116": ("geschichte", 2),     # Monarch
    "Q1397808": ("geschichte", 2), # Widerstandskämpfer
    "Q201788": ("geschichte", 1),  # Historiker
    "Q16533": ("geschichte", 1),   # Richter
    # Geschichte & Gesellschaft (früher Allgemeinwissen)
    "Q4964182": ("geschichte", 2),  # Philosoph
    "Q1234713": ("geschichte", 2),  # Theologe
    "Q250867": ("geschichte", 1),   # katholischer Priester
}

_MUSTER = {kat: [(re.compile(r"(?<!\w)" + re.escape(w)), g) for w, g in woerter.items()]
           for kat, woerter in STICHWORTE.items()}


def punkte(kategorien: list[str], berufe: list[str] = ()) -> dict[str, int]:
    """Punkte pro Quizkategorie aus Wikipedia-Kategorien und Wikidata-Berufen."""
    p = {k: 0 for k in STICHWORTE}
    for name in kategorien:
        n = name.lower().removeprefix("kategorie:")
        for kat, muster in _MUSTER.items():
            p[kat] += max((g for m, g in muster if m.search(n)), default=0)
    for b in set(berufe):
        if b in BERUFE:
            kat, g = BERUFE[b]
            p[kat] += g
    return p


def zuordnen(kategorien: list[str], berufe: list[str] = ()) -> str | None:
    """Ordnet einen Artikel einer Quizkategorie zu; None, wenn nicht eindeutig."""
    p = punkte(kategorien, berufe)
    beste = max(p.values())
    if beste < 2:
        return None
    sieger = [k for k, v in p.items() if v == beste]
    return sieger[0] if len(sieger) == 1 else None
