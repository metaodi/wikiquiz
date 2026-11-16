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
# Von Hand gepflegte Artikel pro Kategorie (Nischenwissen der eigenen Spielrunde), siehe lade_eigene_artikel()
EIGENE_ARTIKEL_DATEI = Path(os.environ.get("WIKIQUIZ_EIGENE_ARTIKEL", GENERATOR_DIR / "eigene_artikel.toml"))

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
    "harrypotter": "Harry Potter",
}

# Themenkategorien liegen quer zu den Fachkategorien (ein Bundesrat wäre sonst „Geschichte“,
# ein Star-Wars-Film „Sport & Unterhaltung“). Für sie entfällt der Kategorie-Abgleich, und
# Exzellente/Lesenswerte Artikel werden ihnen nicht per Stichwort zugeordnet.
THEMENKATEGORIEN: frozenset[str] = frozenset({"schweiz", "starwars", "harrypotter"})

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
# Star Wars: Filme und Serien sind weltweit bekannt; Figuren haben auf de.wikipedia meist keinen
# eigenen Artikel. Bei 50 Aufrufen/Tag kommen u. a. „Jedi“, „Todesstern“ und die Spiele dazu (31 statt 22 Artikel)
SCHWELLEN["starwars"] = Schwellen(min_sitelinks=20, min_pageviews=50.0)
# Harry Potter: Bücher und Filme sind weltweit bekannt, Begriffe (Muggel, Quidditch) und Orte werden
# auf de.wikipedia seltener aufgerufen
SCHWELLEN["harrypotter"] = Schwellen(min_sitelinks=20, min_pageviews=50.0)

# Englische Wikipedia als ergänzende Quelle, pro Kategorie einschaltbar: für Themen, zu denen kein
# deutscher Artikel den Bekanntheitsfilter besteht (Star-Wars-Figuren haben oft nur kurze, kaum
# aufgerufene deutsche Artikel). Startkategorien in wikipedia/quellen.py. Eigene Schwellen, gemessen
# auf en.wikipedia (Tatooine ≈ 220, The Force ≈ 150, BB-8 ≈ 120 Aufrufe/Tag).
EN_SCHWELLEN: dict[str, Schwellen] = {
    "starwars": Schwellen(min_sitelinks=20, min_pageviews=100.0),
    # Harry Potter: Nebenfiguren (Dumbledore, Snape, Ron) stehen auf de.wikipedia nur in Sammelartikeln
    "harrypotter": Schwellen(min_sitelinks=20, min_pageviews=100.0),
}


def lade_eigene_artikel(pfad: Path | None = None) -> dict[str, list[str]]:
    """Eigene Artikel pro Kategorie aus `eigene_artikel.toml` (Titel; englische mit Präfix „en:“).
    Fehlt die Datei, gibt es keine. Unbekannte Kategorien oder falsche Typen sind ein Fehler,
    damit sich Tippfehler nicht still verlieren."""
    import tomllib

    pfad = pfad or EIGENE_ARTIKEL_DATEI
    if not pfad.exists():
        return {}
    with pfad.open("rb") as f:
        roh = tomllib.load(f)
    ergebnis: dict[str, list[str]] = {}
    for kat, titel in roh.items():
        if kat not in KATEGORIEN:
            raise ValueError(f"{pfad.name}: unbekannte Kategorie „{kat}“ (erlaubt: {', '.join(KATEGORIEN)})")
        if not isinstance(titel, list) or not all(isinstance(t, str) for t in titel):
            raise ValueError(f"{pfad.name}: „{kat}“ muss eine Liste von Artikeltiteln sein")
        eindeutig = list(dict.fromkeys(t.strip() for t in titel if t.strip()))
        if eindeutig:
            ergebnis[kat] = eindeutig
    return ergebnis
