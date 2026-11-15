"""Zentrale Konfiguration: Kategorien, Schwellen, Pfade, Umgebungsvariablen."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

GENERATOR_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = GENERATOR_DIR.parent

CACHE_DIR = Path(os.environ.get("WIKIQUIZ_CACHE_DIR", GENERATOR_DIR / "cache"))
OUT_DIR = Path(os.environ.get("WIKIQUIZ_OUT_DIR", GENERATOR_DIR / "out"))
QUESTIONS_PATH = Path(
    os.environ.get("WIKIQUIZ_QUESTIONS", REPO_DIR / "app" / "public" / "questions.json")
)

USER_AGENT = os.environ.get(
    "WIKIQUIZ_USER_AGENT",
    "WikiQuiz-Generator/0.1 (https://github.com/metaodi/wikiquiz; odi@metaodi.ch)",
)

KATEGORIEN: dict[str, str] = {
    "naturwissenschaften": "Naturwissenschaften & Technik",
    "kunst": "Kunst, Musik & Literatur",
    "geschichte": "Geschichte",
    "sport": "Sport & Unterhaltung",
    "geografie": "Geografie",
    "allgemeinwissen": "Allgemeinwissen",
}

LIZENZ = {"wikidata": "CC0", "wikipedia": "CC BY-SA 4.0"}

# Formale Regeln (gelten für alle Quellen)
MAX_FRAGE_ZEICHEN = 120
MAX_ANTWORT_ZEICHEN = 40
MAX_FRAGEN_PRO_QUELLE = 2


@dataclass(frozen=True)
class Schwellen:
    min_sitelinks: int = 30
    min_pageviews: float = 200.0  # Durchschnitt pro Tag über 12 Monate (de.wikipedia)
    min_zeichen: int = 3000  # Klartextlänge des Artikels
    min_ereignis_alter_tage: int = 365


SCHWELLEN: dict[str, Schwellen] = {k: Schwellen() for k in KATEGORIEN}
# Sport & Unterhaltung: Seitenaufrufe hoch, aber kurzlebig → strengerer Sitelink-Filter
SCHWELLEN["sport"] = Schwellen(min_sitelinks=50)
