"""Grammatik für Ländernamen: Länder mit Artikel (Nominativ / Genitiv)."""
from __future__ import annotations

# label → (Nominativ, Genitiv)
MIT_ARTIKEL: dict[str, tuple[str, str]] = {
    "Schweiz": ("die Schweiz", "der Schweiz"),
    "Türkei": ("die Türkei", "der Türkei"),
    "Mongolei": ("die Mongolei", "der Mongolei"),
    "Slowakei": ("die Slowakei", "der Slowakei"),
    "Ukraine": ("die Ukraine", "der Ukraine"),
    "Elfenbeinküste": ("die Elfenbeinküste", "der Elfenbeinküste"),
    "Dominikanische Republik": ("die Dominikanische Republik", "der Dominikanischen Republik"),
    "Zentralafrikanische Republik": ("die Zentralafrikanische Republik", "der Zentralafrikanischen Republik"),
    "Demokratische Republik Kongo": ("die Demokratische Republik Kongo", "der Demokratischen Republik Kongo"),
    "Republik Kongo": ("die Republik Kongo", "der Republik Kongo"),
    "Volksrepublik China": ("die Volksrepublik China", "der Volksrepublik China"),
    "Irak": ("der Irak", "des Irak"),
    "Iran": ("der Iran", "des Iran"),
    "Jemen": ("der Jemen", "des Jemen"),
    "Libanon": ("der Libanon", "des Libanon"),
    "Sudan": ("der Sudan", "des Sudan"),
    "Südsudan": ("der Südsudan", "des Südsudan"),
    "Tschad": ("der Tschad", "des Tschad"),
    "Niger": ("der Niger", "des Niger"),
    "Senegal": ("der Senegal", "des Senegal"),
    "Kosovo": ("der Kosovo", "des Kosovo"),
    "Oman": ("der Oman", "des Oman"),
    "Vatikanstadt": ("die Vatikanstadt", "der Vatikanstadt"),
    "Vereinigtes Königreich": ("das Vereinigte Königreich", "des Vereinigten Königreichs"),
    "Vereinigte Staaten": ("die Vereinigten Staaten", "der Vereinigten Staaten"),
    "Vereinigte Arabische Emirate": ("die Vereinigten Arabischen Emirate", "der Vereinigten Arabischen Emirate"),
    "Niederlande": ("die Niederlande", "der Niederlande"),
    "Philippinen": ("die Philippinen", "der Philippinen"),
    "Malediven": ("die Malediven", "der Malediven"),
    "Seychellen": ("die Seychellen", "der Seychellen"),
    "Komoren": ("die Komoren", "der Komoren"),
    "Bahamas": ("die Bahamas", "der Bahamas"),
    "Salomonen": ("die Salomonen", "der Salomonen"),
    "Marshallinseln": ("die Marshallinseln", "der Marshallinseln"),
    "Föderierte Staaten von Mikronesien": ("die Föderierten Staaten von Mikronesien", "der Föderierten Staaten von Mikronesien"),
}


def nominativ(land: str) -> str:
    return MIT_ARTIKEL.get(land, (land, land))[0]


PLURAL = {
    "Vereinigte Staaten", "Vereinigte Arabische Emirate", "Niederlande", "Philippinen", "Malediven",
    "Seychellen", "Komoren", "Bahamas", "Salomonen", "Marshallinseln", "Föderierte Staaten von Mikronesien",
}


def ist_plural(land: str) -> bool:
    return land in PLURAL


def liegt(land: str) -> str:
    """„liegt Kanada“ / „liegen die Niederlande“."""
    return f"{'liegen' if ist_plural(land) else 'liegt'} {nominativ(land)}"


def hauptstadt_von(land: str) -> str:
    """„von Kanada“ bzw. Genitiv bei Ländern mit Artikel: „der Schweiz“, „des Irak“, „der Niederlande“."""
    if land in MIT_ARTIKEL:
        return MIT_ARTIKEL[land][1]
    return f"von {land}"
