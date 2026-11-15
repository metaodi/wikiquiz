"""Grammatik für Ländernamen: Länder mit Artikel (Nominativ / Dativ nach „von“)."""
from __future__ import annotations

# label → (Nominativ, "von"-Form)
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
    "Irak": ("der Irak", "dem Irak"),
    "Iran": ("der Iran", "dem Iran"),
    "Jemen": ("der Jemen", "dem Jemen"),
    "Libanon": ("der Libanon", "dem Libanon"),
    "Sudan": ("der Sudan", "dem Sudan"),
    "Südsudan": ("der Südsudan", "dem Südsudan"),
    "Tschad": ("der Tschad", "dem Tschad"),
    "Niger": ("der Niger", "dem Niger"),
    "Senegal": ("der Senegal", "dem Senegal"),
    "Kosovo": ("der Kosovo", "dem Kosovo"),
    "Oman": ("der Oman", "dem Oman"),
    "Vatikanstadt": ("die Vatikanstadt", "der Vatikanstadt"),
    "Vereinigtes Königreich": ("das Vereinigte Königreich", "dem Vereinigten Königreich"),
    "Vereinigte Staaten": ("die Vereinigten Staaten", "den Vereinigten Staaten"),
    "Vereinigte Arabische Emirate": ("die Vereinigten Arabischen Emirate", "den Vereinigten Arabischen Emiraten"),
    "Niederlande": ("die Niederlande", "den Niederlanden"),
    "Philippinen": ("die Philippinen", "den Philippinen"),
    "Malediven": ("die Malediven", "den Malediven"),
    "Seychellen": ("die Seychellen", "den Seychellen"),
    "Komoren": ("die Komoren", "den Komoren"),
    "Bahamas": ("die Bahamas", "den Bahamas"),
    "Salomonen": ("die Salomonen", "den Salomonen"),
    "Marshallinseln": ("die Marshallinseln", "den Marshallinseln"),
    "Föderierte Staaten von Mikronesien": ("die Föderierten Staaten von Mikronesien", "den Föderierten Staaten von Mikronesien"),
}


def nominativ(land: str) -> str:
    return MIT_ARTIKEL.get(land, (land, land))[0]


def von(land: str) -> str:
    """„von Kanada“, „von der Schweiz“, „vom Irak“, „von den Niederlanden“."""
    if land not in MIT_ARTIKEL:
        return f"von {land}"
    dativ = MIT_ARTIKEL[land][1]
    if dativ.startswith("dem "):
        return "vom " + dativ[4:]
    return "von " + dativ
