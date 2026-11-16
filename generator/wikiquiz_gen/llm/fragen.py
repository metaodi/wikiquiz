"""Generierung und unabhängige Prüfung von Fragen zu einem Wikipedia-Artikel."""
from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass, field

from ..config import KATEGORIEN
from ..models import Frage, swiss, text_bereinigen
from ..sparql import artikel_url
from ..validate import pruefe_formal
from .client import LLM
from .prompts import GENERIERUNG_SYSTEM, GENERIERUNG_USER, GENERIERUNG_ZUSATZ_EIGEN, PRUEFUNG, fuellen

MIN_BEKANNTHEIT_THEMA = 3
MIN_ALLGEMEINWISSEN = 3

SCHEMA_GENERIERUNG = {
    "type": "object",
    "properties": {
        "bekanntheit_thema": {"type": "integer"},
        "fragen": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "frage": {"type": "string"},
                    "richtige_antwort": {"type": "string"},
                    "falsche_antworten": {"type": "array", "items": {"type": "string"}},
                    "schwierigkeit": {"type": "integer"},
                    "belegstelle": {"type": "string"},
                    "begruendung_bekanntheit": {"type": "string"},
                },
                "required": ["frage", "richtige_antwort", "falsche_antworten", "schwierigkeit",
                             "belegstelle", "begruendung_bekanntheit"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["bekanntheit_thema", "fragen"],
    "additionalProperties": False,
}

SCHEMA_PRUEFUNG = {
    "type": "object",
    "properties": {
        "deine_antwort": {"type": "string"},
        "eindeutig": {"type": "boolean"},
        "allgemeinwissen": {"type": "integer"},
        "probleme": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["deine_antwort", "eindeutig", "allgemeinwissen", "probleme"],
    "additionalProperties": False,
}

_ANFUEHRUNG = str.maketrans({"„": '"', "“": '"', "”": '"', "«": '"', "»": '"', "‚": "'", "‘": "'",
                             "’": "'", "‹": "'", "›": "'", "–": "-", "—": "-", " ": " "})


def normalisiere_beleg(s: str) -> str:
    s = unicodedata.normalize("NFC", s).translate(_ANFUEHRUNG)
    s = swiss(s).lower()
    return re.sub(r"\s+", " ", s).strip()


def beleg_vorhanden(beleg: str, text: str) -> bool:
    """Die Belegstelle muss wörtlich im Text stehen. Auslassungen („…“) sind erlaubt,
    dann muss jedes Teilstück (mind. 3 Wörter) vorkommen. ß/ss und Anführungszeichen werden normalisiert."""
    t = normalisiere_beleg(text)
    teile = [normalisiere_beleg(x).strip(" .,;:\"'") for x in re.split(r"\.\.\.|…|\[…\]|\(…\)", beleg)]
    teile = [x for x in teile if x]
    if not teile:
        return False
    return all(len(x.split()) >= 3 and x in t for x in teile)


def _kurz(s: str) -> str:
    return re.sub(r"[^\w]+", " ", swiss(unicodedata.normalize("NFC", s)).casefold()).strip()


def zuordnen_antwort(antwort: str, optionen: list[str]) -> int | None:
    """Index der Option, die der Prüfer gewählt hat (exakt bzw. eindeutig enthalten)."""
    a = _kurz(antwort)
    exakt = [i for i, o in enumerate(optionen) if _kurz(o) == a]
    if len(exakt) == 1:
        return exakt[0]
    enthalten = [i for i, o in enumerate(optionen) if _kurz(o) and (_kurz(o) in a or a in _kurz(o))]
    return enthalten[0] if len(enthalten) == 1 else None


@dataclass
class ArtikelErgebnis:
    titel: str
    bekanntheit_thema: int | None = None
    angenommen: list[Frage] = field(default_factory=list)
    verworfen: list[tuple[dict, str]] = field(default_factory=list)
    fehler: str | None = None


def bestehende_als_text(bestehende: list[dict]) -> str:
    if not bestehende:
        return "(keine)"
    return "\n".join(f"- {f['frage']} → {f['antworten'][f['korrekt_index']]}" for f in bestehende)


def artikel_verarbeiten(
    gen: LLM,
    pruefer: LLM,
    kategorie: str,
    titel: str,
    qid: str,
    text: str,
    bestehende: list[dict],
    n: int = 2,
    rng: random.Random | None = None,
    sprache: str = "de",
    eigen: bool = False,
) -> ArtikelErgebnis:
    """`sprache`: Wikipedia des Artikeltexts. Fragen sind immer deutsch (auch bei englischem Text).
    `eigen`: Artikel aus eigene_artikel.toml (Nischenwissen der Spielrunde). Das LLM erhält einen Hinweis
    (GENERIERUNG_ZUSATZ_EIGEN); die Schwellen für Bekanntheit des Themas und Allgemeinwissen entfallen."""
    rng = rng or random.Random(titel)
    erg = ArtikelErgebnis(titel)
    nachricht = fuellen(GENERIERUNG_USER, kategorie=KATEGORIEN[kategorie], n=n,
                        bestehende_fragen=bestehende_als_text(bestehende), titel=titel, text=text)
    if eigen:
        nachricht += "\n\n" + GENERIERUNG_ZUSATZ_EIGEN
    antwort = gen.json(
        nachricht,
        SCHEMA_GENERIERUNG,
        system=GENERIERUNG_SYSTEM,
    )
    erg.bekanntheit_thema = antwort["bekanntheit_thema"]
    for roh in antwort["fragen"][:n]:
        daten = {"titel": titel, **roh}
        if not eigen and erg.bekanntheit_thema < MIN_BEKANNTHEIT_THEMA:
            erg.verworfen.append((daten, f"bekanntheit_thema {erg.bekanntheit_thema} < {MIN_BEKANNTHEIT_THEMA}"))
            continue
        f = Frage(
            kategorie=kategorie,
            frage=text_bereinigen(roh["frage"]),
            richtig=text_bereinigen(roh["richtige_antwort"]),
            falsch=[text_bereinigen(x) for x in roh["falsche_antworten"]],
            schwierigkeit=roh["schwierigkeit"],
            quelle_typ="wikipedia",
            quelle_url=artikel_url(titel, sprache),
            quelle_titel=titel,
            quelle_id=qid,
            template="llm",
            meta={"belegstelle": roh["belegstelle"], "begruendung": roh["begruendung_bekanntheit"],
                  "bekanntheit_thema": erg.bekanntheit_thema, "eigen": eigen},
        )
        fehler = pruefe_formal(f)
        if fehler:
            erg.verworfen.append((daten, "formal: " + "; ".join(fehler)))
            continue
        if not beleg_vorhanden(roh["belegstelle"], text):
            erg.verworfen.append((daten, "belegstelle nicht im text"))
            continue

        # Unabhängige Prüfung: gemischte Antworten, ohne Hinweis auf die richtige
        optionen = [f.richtig, *f.falsch]
        rng.shuffle(optionen)
        p = pruefer.json(
            fuellen(PRUEFUNG, frage=f.frage, a=optionen[0], b=optionen[1], c=optionen[2], d=optionen[3], text=text),
            SCHEMA_PRUEFUNG,
        )
        daten["pruefung"] = p
        f.meta["pruefung"] = p
        gewaehlt = zuordnen_antwort(p["deine_antwort"], optionen)
        if gewaehlt is None or optionen[gewaehlt] != f.richtig:
            erg.verworfen.append((daten, f"pruefer antwortet anders: {p['deine_antwort']!r}"))
        elif not p["eindeutig"]:
            erg.verworfen.append((daten, "nicht eindeutig: " + "; ".join(p["probleme"])[:200]))
        elif not eigen and p["allgemeinwissen"] < MIN_ALLGEMEINWISSEN:
            erg.verworfen.append((daten, f"allgemeinwissen {p['allgemeinwissen']} < {MIN_ALLGEMEINWISSEN}"))
        else:
            erg.angenommen.append(f)
    return erg
