"""Datenmodell einer Frage und Umwandlung ins Format von questions.json."""
from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass, field

from .config import LIZENZ


def swiss(text: str) -> str:
    """Schweizer Rechtschreibung: ß → ss."""
    return text.replace("ß", "ss").replace("ẞ", "SS")


def normalisiere(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


@dataclass
class Frage:
    kategorie: str
    frage: str
    richtig: str
    falsch: list[str]
    schwierigkeit: int
    quelle_typ: str  # "wikidata" | "wikipedia"
    quelle_url: str
    quelle_titel: str
    quelle_id: str  # QID oder Artikeltitel
    template: str = ""  # Template-Name bzw. "llm"
    score: float = 0.0  # Sortierung (z. B. Seitenaufrufe)
    meta: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        praefix = "wd" if self.quelle_typ == "wikidata" else "wp"
        h = hashlib.sha1(f"{self.quelle_id}|{normalisiere(self.frage)}".encode()).hexdigest()
        return f"{praefix}-{h[:10]}"

    def to_json(self) -> dict:
        antworten = [self.richtig, *self.falsch]
        # Deterministisch mischen, damit die Datei stabil bleibt (App mischt zur Laufzeit erneut)
        random.Random(self.id).shuffle(antworten)
        return {
            "id": self.id,
            "kategorie": self.kategorie,
            "frage": self.frage,
            "antworten": antworten,
            "korrekt_index": antworten.index(self.richtig),
            "schwierigkeit": self.schwierigkeit,
            "quelle_typ": self.quelle_typ,
            "quelle_url": self.quelle_url,
            "lizenz": LIZENZ[self.quelle_typ],
            "quelle_titel": self.quelle_titel,
            "quelle_id": self.quelle_id,
        }
