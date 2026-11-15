"""Schreiben von questions.json und rejected.jsonl."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import OUT_DIR, QUESTIONS_PATH


def jetzt_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def lade_pool(pfad: Path = QUESTIONS_PATH) -> dict:
    if pfad.exists():
        return json.loads(pfad.read_text(encoding="utf-8"))
    return {"version": 1, "generiert_am": None, "fragen": []}


def schreibe_pool(
    neue: list[dict],
    bereiche: set[tuple[str, str]],
    modus: str = "ersetzen",
    pfad: Path = QUESTIONS_PATH,
) -> dict:
    """Fügt `neue` Fragen in den Pool ein.

    modus="ersetzen": bestehende Fragen der Bereiche (kategorie, quelle_typ) werden ersetzt.
    modus="ergaenzen": bestehende Fragen bleiben, nur neue IDs kommen dazu.
    """
    pool = lade_pool(pfad)
    alte = pool["fragen"]
    if modus == "ersetzen":
        alte = [f for f in alte if (f["kategorie"], f["quelle_typ"]) not in bereiche]
    vorhandene = {f["id"] for f in alte}
    fragen = alte + [f for f in neue if f["id"] not in vorhandene]
    fragen.sort(key=lambda f: (f["kategorie"], f["quelle_typ"], f["id"]))
    pool = {"version": 1, "generiert_am": jetzt_iso(), "fragen": fragen}
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(pool, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return pool


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
