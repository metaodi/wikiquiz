"""Zentrale Konfiguration: Kategorien, Schwellen, Pfade, Umgebungsvariablen."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

GENERATOR_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = GENERATOR_DIR.parent

CACHE_DIR = Path(os.environ.get("WIKIQUIZ_CACHE_DIR", GENERATOR_DIR / "cache"))
OUT_DIR = Path(os.environ.get("WIKIQUIZ_OUT_DIR", GENERATOR_DIR / "out"))
# Fragen pro Kategorie (committet); der App-Build fügt sie zu questions.json zusammen
DATA_DIR = Path(os.environ.get("WIKIQUIZ_DATA_DIR", REPO_DIR / "data" / "fragen"))

USER_AGENT = os.environ.get(
    "WIKIQUIZ_USER_AGENT",
    "WikiQuiz-Generator/0.1 (https://github.com/metaodi/wikiquiz; odi@metaodi.ch)",
)

KATEGORIEN: dict[str, str] = {
    "naturwissenschaften": "Naturwissenschaften & Technik",
    "kunst": "Kunst, Musik & Literatur",
    "geschichte": "Geschichte & Gesellschaft",
    "sport": "Sport & Unterhaltung",
    "geografie": "Geografie",
    "essen": "Essen & Genuss",
    "natur": "Tiere & Natur",
    "schweiz": "Schweiz",
    "starwars": "Star Wars",
}

# Themenkategorien liegen quer zu den Fachkategorien (ein Bundesrat wäre sonst „Geschichte“,
# ein Star-Wars-Film „Sport & Unterhaltung“). Für sie entfällt der Kategorie-Abgleich, und
# Exzellente/Lesenswerte Artikel werden ihnen nicht per Stichwort zugeordnet.
THEMENKATEGORIEN: frozenset[str] = frozenset({"schweiz", "starwars"})

LIZENZ = {"wikidata": "CC0", "wikipedia": "CC BY-SA 4.0"}

# Formale Regeln (gelten für alle Quellen)
MAX_FRAGE_ZEICHEN = 120
MAX_ANTWORT_ZEICHEN = 40
MAX_FRAGEN_PRO_QUELLE = 2


@dataclass(frozen=True)
class Schwellen:
    min_sitelinks: int = 30
    min_pageviews: float = 200.0  # Durchschnitt pro Tag über 12 Monate (de.wikipedia)
    # Für die richtige Antwort (z. B. Hauptstadt): Städteartikel werden seltener aufgerufen
    # als Länderartikel (Ankara ≈ 170/Tag, Nairobi ≈ 150/Tag)
    min_pageviews_antwort: float = 100.0
    min_zeichen: int = 3000  # Klartextlänge des Artikels
    min_ereignis_alter_tage: int = 365


SCHWELLEN: dict[str, Schwellen] = {k: Schwellen() for k in KATEGORIEN}
# Sport & Unterhaltung: Seitenaufrufe hoch, aber kurzlebig → strengerer Sitelink-Filter
SCHWELLEN["sport"] = Schwellen(min_sitelinks=50)
# Kunst, Musik & Literatur: zeitgenössische Personen mit kurzfristig hohen Seitenaufrufen
# (z. B. nach Preisverleihungen) ausschliessen
SCHWELLEN["kunst"] = Schwellen(min_sitelinks=50)
# Naturwissenschaften & Technik: Fachartikel werden auf de.wikipedia deutlich seltener aufgerufen
# (Niels Bohr, Enrico Fermi, Elektron < 200/Tag), sind aber Allgemeinwissen
SCHWELLEN["naturwissenschaften"] = Schwellen(min_pageviews=100.0)
# Schweiz: Schweizer Themen haben weniger Sprachversionen und Aufrufe als weltweit bekannte
# (Bundesräte, Kantone, Pässe). Die Bekanntheit prüft zusätzlich das LLM (Allgemeinwissen ≥ 3).
SCHWELLEN["schweiz"] = Schwellen(min_sitelinks=15, min_pageviews=100.0)
# Star Wars: Filme und Hauptfiguren sind weltweit bekannt, Nebenfiguren und Romane nicht
SCHWELLEN["starwars"] = Schwellen(min_sitelinks=20, min_pageviews=100.0)
