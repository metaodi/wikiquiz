"""Fragenablage pro Kategorie (data/fragen/<kategorie>.json) und Protokoll verworfener Fragen.

Eine Datei pro Kategorie, damit parallele Pull Requests (z. B. aus der GitHub Action) nicht
miteinander in Konflikt geraten. Der App-Build fügt die Dateien zu questions.json zusammen.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import DATA_DIR, KATEGORIEN, OUT_DIR


def jetzt_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def kategorie_pfad(kategorie: str, verzeichnis: Path | None = None) -> Path:
    return (verzeichnis or DATA_DIR) / f"{kategorie}.json"


def lade_kategorie(kategorie: str, verzeichnis: Path | None = None) -> list[dict]:
    pfad = kategorie_pfad(kategorie, verzeichnis)
    if pfad.exists():
        return json.loads(pfad.read_text(encoding="utf-8"))["fragen"]
    return []


def lade_alle(verzeichnis: Path | None = None) -> list[dict]:
    return [f for kat in KATEGORIEN for f in lade_kategorie(kat, verzeichnis)]


def schreibe_kategorie(
    kategorie: str,
    neue: list[dict],
    quellen: set[str],
    modus: str = "ergaenzen",
    verzeichnis: Path | None = None,
) -> list[dict]:
    """Fügt `neue` Fragen in die Datei der Kategorie ein.

    modus="ersetzen": bestehende Fragen der Quellen (`quelle_typ`) werden ersetzt.
    modus="ergaenzen": bestehende Fragen bleiben unverändert, nur neue IDs kommen dazu.
    """
    alte = lade_kategorie(kategorie, verzeichnis)
    if modus == "ersetzen":
        alte = [f for f in alte if f["quelle_typ"] not in quellen]
    vorhandene = {f["id"] for f in alte}
    return speichere_kategorie(kategorie, alte + [f for f in neue if f["id"] not in vorhandene], verzeichnis)


def ersetzbare_quellen(modus: str, quellen: set[str]) -> set[str]:
    """Welche Quellen ein Lauf ersetzen darf. Nur Wikidata-Fragen (deterministisch neu erzeugbar);
    Wikipedia-Fragen werden immer nur ergänzt, sonst gingen bereits bezahlte Fragen verloren."""
    return quellen & {"wikidata"} if modus == "ersetzen" else set()


def speichere_kategorie(kategorie: str, fragen: list[dict], verzeichnis: Path | None = None) -> list[dict]:
    """Schreibt alle Fragen einer Kategorie (sortiert, damit Diffs klein bleiben)."""
    fragen = sorted(fragen, key=lambda f: (f["quelle_typ"], f["id"]))
    pfad = kategorie_pfad(kategorie, verzeichnis)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    inhalt = {"version": 1, "kategorie": kategorie, "generiert_am": jetzt_iso(), "fragen": fragen}
    pfad.write_text(json.dumps(inhalt, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return fragen


def verschieben(ids: list[str], nach: str, verzeichnis: Path | None = None) -> list[dict]:
    """Verschiebt Fragen per ID in eine andere Kategorie. Die IDs bleiben gleich
    (sie hängen nur von Quelle und Fragetext ab). Gibt die verschobenen Fragen zurück."""
    gesucht = set(ids)
    verschoben: list[dict] = []
    for kat in KATEGORIEN:
        if kat == nach:
            continue
        fragen = lade_kategorie(kat, verzeichnis)
        bleiben = [f for f in fragen if f["id"] not in gesucht]
        if len(bleiben) != len(fragen):
            verschoben += [{**f, "kategorie": nach} for f in fragen if f["id"] in gesucht]
            speichere_kategorie(kat, bleiben, verzeichnis)
    fehlend = gesucht - {f["id"] for f in verschoben}
    if fehlend:
        raise ValueError(f"Nicht gefunden (oder schon in {nach}): {', '.join(sorted(fehlend))}")
    ziel = lade_kategorie(nach, verzeichnis)
    speichere_kategorie(nach, ziel + verschoben, verzeichnis)
    return verschoben


def entfernen(ids: list[str], verzeichnis: Path | None = None) -> list[dict]:
    """Löscht Fragen per ID aus allen Kategorien. Gibt die entfernten Fragen zurück.
    Der Artikel bleibt in data/verarbeitet/ vermerkt, damit er nicht erneut verarbeitet wird."""
    gesucht = set(ids)
    entfernt: list[dict] = []
    for kat in KATEGORIEN:
        fragen = lade_kategorie(kat, verzeichnis)
        bleiben = [f for f in fragen if f["id"] not in gesucht]
        if len(bleiben) != len(fragen):
            entfernt += [f for f in fragen if f["id"] in gesucht]
            speichere_kategorie(kat, bleiben, verzeichnis)
    fehlend = gesucht - {f["id"] for f in entfernt}
    if fehlend:
        raise ValueError(f"Nicht gefunden: {', '.join(sorted(fehlend))}")
    return entfernt


class Protokoll:
    """Verworfene Kandidaten/Fragen mit Grund → out/rejected.jsonl"""

    def __init__(self, pfad: Path | None = None, aktiv: bool = True) -> None:
        self.pfad = pfad or OUT_DIR / "rejected.jsonl"
        self.aktiv = aktiv
        self.lauf = jetzt_iso()
        self.eintraege: list[dict] = []

    def verwerfen(self, kategorie: str, stufe: str, grund: str, daten: dict) -> None:
        self.eintraege.append(
            {"lauf": self.lauf, "kategorie": kategorie, "stufe": stufe, "grund": grund, **daten}
        )

    def speichern(self) -> None:
        if not self.aktiv or not self.eintraege:
            return
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        with self.pfad.open("a", encoding="utf-8") as fh:
            for e in self.eintraege:
                fh.write(json.dumps(e, ensure_ascii=False, default=str) + "\n")


# Bereits verarbeitete Wikipedia-Artikel (verhindert erneute, kostenpflichtige LLM-Aufrufe)
def verarbeitet_pfad(kategorie: str, verzeichnis: Path | None = None) -> Path:
    return (verzeichnis or DATA_DIR.parent / "verarbeitet") / f"{kategorie}.json"


def lade_verarbeitet(kategorie: str, verzeichnis: Path | None = None) -> dict[str, dict]:
    pfad = verarbeitet_pfad(kategorie, verzeichnis)
    return json.loads(pfad.read_text(encoding="utf-8")) if pfad.exists() else {}


def schreibe_verarbeitet(kategorie: str, eintraege: dict[str, dict], verzeichnis: Path | None = None) -> None:
    pfad = verarbeitet_pfad(kategorie, verzeichnis)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(dict(sorted(eintraege.items())), ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
