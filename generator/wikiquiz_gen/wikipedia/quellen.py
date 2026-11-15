"""Quellen für Wikipedia-Artikel pro Quizkategorie.

1. Thematische Kategorien der deutschsprachigen Wikipedia (mit begrenzter Suchtiefe)
2. „Exzellente“ und „Lesenswerte“ Artikel, über ihre Wikipedia-Kategorien per Stichwort zugeordnet

Danach greift der gemeinsame Bekanntheitsfilter (Sitelinks, Seitenaufrufe, Länge …).
"""
from __future__ import annotations

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
    ],
    "geografie": [
        ("Hauptstadt in Europa", 0),
        ("Fluss", 1),
        ("Gebirge", 1),
        ("Insel", 1),
        ("See", 1),
    ],
    "allgemeinwissen": [
        ("Feiertag", 0),
        ("Weltreligion", 0),
        ("Lebensmittel", 1),
        ("Getränk", 1),
        ("Haustier", 1),
        ("Nutztier", 1),
        ("Säugetiere", 0),
        ("Brauch", 1),
        ("Spiel", 1),
        ("Sprache", 0),
    ],
}

QUALITAETSKATEGORIEN = ["Wikipedia:Exzellent", "Wikipedia:Lesenswert"]

# Stichworte in den (nicht versteckten) Kategorien eines Artikels → Quizkategorie.
# Gewicht 2 für eindeutige Stichworte. Zuordnung nur bei eindeutigem Höchstwert.
STICHWORTE: dict[str, dict[str, int]] = {
    "naturwissenschaften": {
        "physik": 2, "chemi": 2, "biolog": 1, "astronom": 2, "mathemat": 2, "medizin": 1,
        "krankheit": 2, "erfind": 2, "informatik": 2, "chemisches element": 2, "planet": 2,
        "galaxie": 2, "geolog": 1, "anatomie": 2, "genetik": 2, "raumfahrt": 2, "technik": 1,
        "nobelpreisträger für": 1, "naturwissenschaftler": 2, "elektr": 1,
    },
    "kunst": {
        "maler": 2, "malerei": 2, "gemälde": 2, "komponist": 2, "oper": 2, "literatur": 2,
        "roman": 2, "schriftsteller": 1, "autor": 1, "dichter": 2, "lyrik": 2, "drama": 1,
        "bildhauer": 2, "skulptur": 2, "architekt": 1, "theater": 1, "ballett": 2,
        "klassische musik": 2, "musikinstrument": 2, "museum": 1,
    },
    "geschichte": {
        "geschichte": 1, "krieg": 2, "schlacht": 2, "herrscher": 2, "kaiser": 2, "könig": 1,
        "pharao": 2, "dynastie": 2, "revolution": 2, "antike": 1, "mittelalter": 1,
        "imperium": 2, "präsident": 1, "bundeskanzler": 2, "archäolog": 1, "militär": 1,
    },
    "sport": {
        "sport": 2, "fußball": 2, "olympi": 2, "tennis": 2, "film": 2, "fernseh": 2,
        "serie": 1, "schauspieler": 2, "popmusik": 2, "rockmusik": 2, "rockband": 2, "sänger": 1,
        "computerspiel": 2, "comic": 2, "weltmeister": 2,
    },
    "geografie": {
        "fluss": 2, "gebirge": 2, "berg in": 2, "insel": 2, "see in": 2, "hauptstadt": 2,
        "geographie": 2, "geografie": 2, "nationalpark": 2, "wüste": 2, "landschaft": 1,
        "staat in": 2, "ort in": 1, "stadt in": 1,
    },
    "allgemeinwissen": {
        "lebensmittel": 2, "getränk": 2, "feiertag": 2, "religion": 1, "sprache": 1,
        "säugetier": 1, "haustier": 2, "nutztier": 2, "pflanze": 1, "brauch": 2, "spiel": 1,
        "kleidung": 2, "speise": 2, "küche": 1,
    },
}


def zuordnen(kategorien: list[str]) -> str | None:
    """Ordnet einen Artikel anhand seiner Wikipedia-Kategorien einer Quizkategorie zu."""
    punkte = {k: 0 for k in STICHWORTE}
    for name in kategorien:
        n = name.lower().removeprefix("kategorie:")
        for kat, woerter in STICHWORTE.items():
            punkte[kat] += max((g for w, g in woerter.items() if w in n), default=0)
    beste = max(punkte.values())
    if beste < 2:
        return None
    sieger = [k for k, p in punkte.items() if p == beste]
    return sieger[0] if len(sieger) == 1 else None
