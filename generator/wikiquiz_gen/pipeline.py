"""Ablauf: Templates → formale Prüfung → Deduplizierung → Auswahl."""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from .dedupe import deduplizieren
from .models import Frage
from .templates import geografie
from .templates.base import Kontext
from .validate import pruefe_formal

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .llm.client import Verbrauch

WIKIDATA_TEMPLATES: dict[str, Callable[[Kontext], dict[str, list[Frage]]]] = {
    "geografie": geografie.generiere,
}


def reissverschluss(gruppen: dict[str, list[Frage]]) -> list[Frage]:
    """Abwechselnd aus jedem Template, jeweils die bekanntesten zuerst."""
    listen = [sorted(g, key=lambda f: -f.score) for g in gruppen.values()]
    ergebnis = []
    i = 0
    while any(i < len(l) for l in listen):
        ergebnis += [l[i] for l in listen if i < len(l)]
        i += 1
    return ergebnis


def wikidata(ktx: Kontext, ziel: int | None) -> list[Frage]:
    gen = WIKIDATA_TEMPLATES.get(ktx.kategorie)
    if gen is None:
        log.warning("Keine Wikidata-Templates für %s", ktx.kategorie)
        return []
    gruppen = gen(ktx)
    for name, fragen in gruppen.items():
        log.info("Template %-12s %4d Rohfragen", name, len(fragen))

    gueltig: dict[str, list[Frage]] = {}
    for name, fragen in gruppen.items():
        gueltig[name] = []
        for f in fragen:
            fehler = pruefe_formal(f)
            if fehler:
                ktx.protokoll.verwerfen(ktx.kategorie, "formal", "; ".join(fehler),
                                        {"frage": f.frage, "richtig": f.richtig, "falsch": f.falsch,
                                         "quelle_id": f.quelle_id})
            else:
                gueltig[name].append(f)

    sortiert = reissverschluss(gueltig)
    behalten, verworfen = deduplizieren(sortiert)
    for f, grund in verworfen:
        ktx.protokoll.verwerfen(ktx.kategorie, "dedupe", grund,
                                {"frage": f.frage, "richtig": f.richtig, "quelle_id": f.quelle_id})
    if ziel is not None:
        behalten = behalten[:ziel]
    return behalten


# ---------------------------------------------------------------------------
# Wikipedia-Artikel + LLM
# ---------------------------------------------------------------------------
def wikipedia(
    ktx: Kontext,
    ziel: int,
    max_artikel: int,
    bestand: list[dict],
    verarbeitet: dict[str, dict],
    threads: int = 4,
    nur_kandidaten: bool = False,
) -> tuple[list[Frage], dict[str, dict], "Verbrauch | None"]:
    """Erzeugt bis zu (ziel − vorhandene Wikipedia-Fragen) neue Fragen.

    `verarbeitet` (Titel → Ergebnis) verhindert, dass Artikel in späteren Läufen erneut
    (kostenpflichtig) verarbeitet werden. Gibt (neue Fragen, neue Einträge für verarbeitet, Verbrauch) zurück.
    """
    from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

    from .llm.client import LLM, AnmeldeFehler, LLMFehler, Verbrauch
    from .llm.fragen import artikel_verarbeiten
    from .output import jetzt_iso
    from .wikipedia.auszug import auszug, klartext
    from .wikipedia.kandidaten import passende_kategorie, sammeln

    vorhanden = sum(1 for f in bestand if f["quelle_typ"] == "wikipedia")
    bedarf = ziel - vorhanden
    log.info("%s: %d Wikipedia-Fragen vorhanden, Ziel %d → Bedarf %d", ktx.kategorie, vorhanden, ziel, bedarf)
    if bedarf <= 0:
        return [], {}, None

    verbrauch = Verbrauch()
    if not nur_kandidaten:
        # Vor der (langen) Artikelsuche prüfen, ob die Anmeldung bei Anthropic klappt
        gen, pruefer = LLM.generierung(verbrauch), LLM.pruefung(verbrauch)
        gen.pruefe_anmeldung()
        if pruefer.modell != gen.modell:
            pruefer.pruefe_anmeldung()
        log.info("Anmeldung bei Anthropic ok (Generierung: %s, Prüfung: %s)", gen.modell, pruefer.modell)

    roh = sammeln(ktx.http, ktx.kategorie, ktx.schwellen.min_sitelinks)
    kandidaten = ktx.filtern([k for k in roh if k.titel not in verarbeitet], "artikel")
    kandidaten, falsche_kategorie = passende_kategorie(ktx.http, kandidaten, ktx.kategorie)
    for k, grund in falsche_kategorie:
        ktx.protokoll.verwerfen(ktx.kategorie, "kategorie", grund, {"titel": k.titel})
    if falsche_kategorie:
        log.info("%s: %d Artikel passen thematisch zu einer anderen Kategorie, z. B. %s",
                 ktx.kategorie, len(falsche_kategorie),
                 ", ".join(f"{k.titel} ({g.split(': ')[1]})" for k, g in falsche_kategorie[:5]))
    kandidaten.sort(key=lambda k: -(k.pageviews or 0))
    pro_quelle: dict[str, list[dict]] = {}
    for f in bestand:
        pro_quelle.setdefault(f.get("quelle_id", ""), []).append(f)
    kandidaten = [k for k in kandidaten if len(pro_quelle.get(k.qid, [])) < 2]
    log.info("%s: %d neue Artikel bestehen den Bekanntheitsfilter, davon werden höchstens %d verarbeitet",
             ktx.kategorie, len(kandidaten), max_artikel)
    kandidaten = kandidaten[:max_artikel]
    if nur_kandidaten:
        for k in kandidaten:
            print(f"  {k.titel:45} sitelinks {k.sitelinks:4}  pv/Tag {k.pageviews:7.0f}  [{k.extra['quelle']}]")
        return [], {}, None

    neue: list[Frage] = []
    neu_verarbeitet: dict[str, dict] = {}
    fehler: list[str] = []

    def bearbeiten(k):
        text = auszug(klartext(ktx.http, k.titel))
        if len(text) < 800:
            return k, None, "auszug zu kurz"
        best = pro_quelle.get(k.qid, [])
        return k, artikel_verarbeiten(gen, pruefer, ktx.kategorie, k.titel, k.qid, text, best,
                                      n=2 - len(best), rng=ktx.rng("llm", k.titel)), None

    offen = iter(kandidaten)
    with ThreadPoolExecutor(threads) as ex:
        laufend = set()
        while True:
            while len(laufend) < threads and len(neue) < bedarf:
                k = next(offen, None)
                if k is None:
                    break
                laufend.add(ex.submit(bearbeiten, k))
            if not laufend:
                break
            fertig, laufend = wait(laufend, return_when=FIRST_COMPLETED)
            for fut in fertig:
                try:
                    k, erg, grund = fut.result()
                except AnmeldeFehler:
                    for f in laufend:
                        f.cancel()
                    raise
                except LLMFehler as e:
                    log.warning("LLM-Fehler: %s", e)
                    fehler.append(str(e))
                    continue
                eintrag = {"qid": k.qid, "datum": jetzt_iso()[:10]}
                if erg is None:
                    eintrag["grund"] = grund
                    ktx.protokoll.verwerfen(ktx.kategorie, "artikel", grund, {"titel": k.titel})
                else:
                    eintrag.update({"bekanntheit_thema": erg.bekanntheit_thema,
                                    "angenommen": len(erg.angenommen), "verworfen": len(erg.verworfen)})
                    for daten, g in erg.verworfen:
                        ktx.protokoll.verwerfen(ktx.kategorie, "llm", g, daten)
                    neue += erg.angenommen
                    log.info("%-40s bekanntheit %s · %d angenommen · %d verworfen · total %d/%d · %.2f USD",
                             k.titel[:40], erg.bekanntheit_thema, len(erg.angenommen), len(erg.verworfen),
                             len(neue), bedarf, verbrauch.kosten_usd)
                neu_verarbeitet[k.titel] = eintrag

    # Scheitern alle Artikel am LLM, liegt ein grundsätzliches Problem vor (Modellname, Konfiguration)
    if fehler and not neu_verarbeitet:
        raise LLMFehler(f"Alle {len(fehler)} Artikel scheiterten am LLM, zuletzt: {fehler[-1]}")
    if fehler:
        log.warning("%d Artikel wegen LLM-Fehlern übersprungen (werden im nächsten Lauf erneut versucht)",
                    len(fehler))

    # Gegen den Bestand deduplizieren (Bestand hat Vorrang)
    behalten, verworfen = deduplizieren([*(_aus_json(f) for f in bestand), *neue])
    ids_bestand = {f["id"] for f in bestand}
    ergebnis = [f for f in behalten if f.id not in ids_bestand and f.quelle_typ == "wikipedia"]
    for f, grund in verworfen:
        if f.id not in ids_bestand:
            ktx.protokoll.verwerfen(ktx.kategorie, "dedupe", grund,
                                    {"frage": f.frage, "richtig": f.richtig, "titel": f.quelle_titel})
    return ergebnis[:bedarf], neu_verarbeitet, verbrauch


def _aus_json(d: dict) -> Frage:
    """Bestehende Frage (questions.json-Format) für die Deduplizierung zurückverwandeln."""
    richtig = d["antworten"][d["korrekt_index"]]
    f = Frage(
        kategorie=d["kategorie"], frage=d["frage"], richtig=richtig,
        falsch=[a for i, a in enumerate(d["antworten"]) if i != d["korrekt_index"]],
        schwierigkeit=d["schwierigkeit"], quelle_typ=d["quelle_typ"], quelle_url=d["quelle_url"],
        quelle_titel=d.get("quelle_titel", ""), quelle_id=d.get("quelle_id", ""),
    )
    return f
