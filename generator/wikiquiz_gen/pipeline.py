"""Ablauf: Templates → formale Prüfung → Deduplizierung → Auswahl."""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from .dedupe import deduplizieren
from .models import Frage
from .templates import geografie, naturwissenschaften, schweiz
from .templates.base import Kontext
from .validate import pruefe_formal

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .llm.client import Verbrauch

WIKIDATA_TEMPLATES: dict[str, Callable[[Kontext], dict[str, list[Frage]]]] = {
    "geografie": geografie.generiere,
    "naturwissenschaften": naturwissenschaften.generiere,
    "schweiz": schweiz.generiere,
}


def themen_anderer_kategorien(kandidaten: list, andere: list[dict]) -> tuple[list, list[tuple[object, str]]]:
    """Artikel überspringen, zu denen eine andere Kategorie schon Fragen hat (gleiche Wikidata-QID).
    Ein Artikel passt oft zu mehreren Kategorien (Kaki: Essen und Natur, Hermann Hesse: Kunst und Schweiz).
    Das LLM formuliert dann oft wortgleiche Fragen; das kostet doppelt und ergibt doppelte IDs."""
    kat_von = {f["quelle_id"]: f["kategorie"] for f in andere if f.get("quelle_id")}
    behalten, verworfen = [], []
    for k in kandidaten:
        if k.qid in kat_von:
            verworfen.append((k, f"schon in kategorie {kat_von[k.qid]}"))
        else:
            behalten.append(k)
    return behalten, verworfen


def ohne_fremde_ids(neue: list[dict], andere: list[dict]) -> tuple[list[dict], list[dict]]:
    """Letzte Sicherung vor dem Schreiben: Fragen, deren ID es in einer anderen Kategorie schon gibt,
    fallen weg (sonst bricht das Zusammenführen zu questions.json ab)."""
    ids = {f["id"] for f in andere}
    return [f for f in neue if f["id"] not in ids], [f for f in neue if f["id"] in ids]


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
    andere: list[dict] = (),
) -> tuple[list[Frage], dict[str, dict], "Verbrauch | None"]:
    """Erzeugt bis zu (ziel − vorhandene Wikipedia-Fragen) neue Fragen.

    Dazu kommen Fragen zu den eigenen Artikeln der Kategorie (eigene_artikel.toml): ohne Bekanntheitsfilter,
    vor allen anderen und auch dann, wenn das Ziel schon erreicht ist (zählen aber zu `max_artikel`).
    `verarbeitet` (Titel → Ergebnis) verhindert, dass Artikel in späteren Läufen erneut
    (kostenpflichtig) verarbeitet werden. Gibt (neue Fragen, neue Einträge für verarbeitet, Verbrauch) zurück.
    """
    from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

    from .config import lade_eigene_artikel
    from .llm.client import LLM, AnmeldeFehler, LLMFehler, Verbrauch
    from .llm.fragen import artikel_verarbeiten
    from .output import jetzt_iso
    from .wikipedia.auszug import auszug, klartext
    from .wikipedia.kandidaten import amtierende, eigene_kandidaten

    vorhanden = sum(1 for f in bestand if f["quelle_typ"] == "wikipedia")
    bedarf = max(ziel - vorhanden, 0)
    log.info("%s: %d Wikipedia-Fragen vorhanden, Ziel %d → Bedarf %d", ktx.kategorie, vorhanden, ziel, bedarf)
    pro_quelle: dict[str, list[dict]] = {}
    for f in bestand:
        pro_quelle.setdefault(f.get("quelle_id", ""), []).append(f)
    eigene = _eigene(ktx, lade_eigene_artikel().get(ktx.kategorie, []), verarbeitet, pro_quelle,
                     eigene_kandidaten)
    if bedarf <= 0 and not eigene:
        return [], {}, None

    verbrauch = Verbrauch()
    if not nur_kandidaten:
        # Vor der (langen) Artikelsuche prüfen, ob die Anmeldung bei Anthropic klappt
        gen, pruefer = LLM.generierung(verbrauch), LLM.pruefung(verbrauch)
        gen.pruefe_anmeldung()
        if pruefer.modell != gen.modell:
            pruefer.pruefe_anmeldung()
        log.info("Anmeldung bei Anthropic ok (Generierung: %s, Prüfung: %s)", gen.modell, pruefer.modell)

    kandidaten, alle_roh, schwelle = [], [], {"de": ktx.schwellen.min_pageviews}
    if bedarf > 0:
        kandidaten, alle_roh, schwelle = _automatische_auswahl(ktx, verarbeitet, {k.qid for k in eigene})
    kandidaten = eigene + kandidaten
    aktiv = amtierende(ktx.http, [k.qid for k in kandidaten])
    for k in kandidaten:
        if k.qid in aktiv:
            ktx.protokoll.verwerfen(ktx.kategorie, "kategorie", "amtierende person", {"titel": k.titel})
    if aktiv:
        log.info("%s: %d amtierende Personen übersprungen: %s", ktx.kategorie, len(aktiv),
                 ", ".join(k.titel for k in kandidaten if k.qid in aktiv))
    kandidaten = [k for k in kandidaten if k.qid not in aktiv]
    kandidaten, fremd = themen_anderer_kategorien(kandidaten, list(andere))
    for k, grund in fremd:
        ktx.protokoll.verwerfen(ktx.kategorie, "kategorie", grund, {"titel": k.schluessel})
    if fremd:
        log.info("%s: %d Artikel haben schon Fragen in einer anderen Kategorie, z. B. %s", ktx.kategorie,
                 len(fremd), ", ".join(f"{k.titel} ({g.rsplit(' ', 1)[1]})" for k, g in fremd[:5]))
    eigene = [k for k in kandidaten if k.extra.get("eigen")]
    kandidaten = [k for k in kandidaten if not k.extra.get("eigen")]
    # Bekannteste zuerst, gemessen an der Schwelle der jeweiligen Sprache
    kandidaten.sort(key=lambda k: -(k.pageviews or 0) / schwelle[k.sprache])
    kandidaten = [k for k in kandidaten if len(pro_quelle.get(k.qid, [])) < 2]
    if bedarf > 0:
        log.info("%s: %d neue Artikel bestehen den Bekanntheitsfilter, davon werden höchstens %d verarbeitet",
                 ktx.kategorie, len(kandidaten), max(max_artikel - len(eigene), 0))
        kandidaten = _themen_ausgleichen(ktx, alle_roh, kandidaten, bestand)
    if eigene:
        log.info("%s: %d eigene Artikel werden zuerst verarbeitet: %s", ktx.kategorie, len(eigene),
                 ", ".join(k.schluessel for k in eigene))
    kandidaten = (eigene + kandidaten)[:max_artikel]
    if nur_kandidaten:
        for k in kandidaten:
            pv = "      –" if k.pageviews is None else f"{k.pageviews:7.0f}"
            print(f"  {k.schluessel:45} sitelinks {k.sitelinks:4}  pv/Tag {pv}  [{k.extra['quelle']}]")
        return [], {}, None

    neue: list[Frage] = []  # aus der automatischen Auswahl, begrenzt durch `bedarf`
    neue_eigene: list[Frage] = []  # aus eigenen Artikeln, unbegrenzt
    neu_verarbeitet: dict[str, dict] = {}
    fehler: list[str] = []

    def bearbeiten(k):
        text = auszug(klartext(ktx.http, k.titel, k.sprache))
        if len(text) < 800:
            return k, None, "auszug zu kurz"
        best = pro_quelle.get(k.qid, [])
        return k, artikel_verarbeiten(gen, pruefer, ktx.kategorie, k.titel, k.qid, text, best,
                                      n=2 - len(best), rng=ktx.rng("llm", k.titel), sprache=k.sprache,
                                      eigen=bool(k.extra.get("eigen"))), None

    offen = iter(kandidaten)
    with ThreadPoolExecutor(threads) as ex:
        laufend = set()
        while True:
            while len(laufend) < threads:
                # Eigene Artikel stehen vorne und werden immer verarbeitet, die übrigen nur bis zum Bedarf
                k = next(offen, None)
                if k is None or (not k.extra.get("eigen") and len(neue) >= bedarf):
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
                    ktx.protokoll.verwerfen(ktx.kategorie, "artikel", grund, {"titel": k.schluessel})
                else:
                    eintrag.update({"bekanntheit_thema": erg.bekanntheit_thema,
                                    "angenommen": len(erg.angenommen), "verworfen": len(erg.verworfen)})
                    for daten, g in erg.verworfen:
                        ktx.protokoll.verwerfen(ktx.kategorie, "llm", g, daten)
                    if k.extra.get("eigen"):
                        eintrag["eigen"] = True
                        neue_eigene += erg.angenommen
                    else:
                        neue += erg.angenommen
                    log.info("%-40s bekanntheit %s · %d angenommen · %d verworfen · total %d/%d%s · %.2f USD",
                             k.titel[:40], erg.bekanntheit_thema, len(erg.angenommen), len(erg.verworfen),
                             len(neue), bedarf, f" + {len(neue_eigene)} eigene" if neue_eigene else "",
                             verbrauch.kosten_usd)
                neu_verarbeitet[k.schluessel] = eintrag

    # Scheitern alle Artikel am LLM, liegt ein grundsätzliches Problem vor (Modellname, Konfiguration)
    if fehler and not neu_verarbeitet:
        raise LLMFehler(f"Alle {len(fehler)} Artikel scheiterten am LLM, zuletzt: {fehler[-1]}")
    if fehler:
        log.warning("%d Artikel wegen LLM-Fehlern übersprungen (werden im nächsten Lauf erneut versucht)",
                    len(fehler))

    # Gegen den Bestand deduplizieren (Bestand hat Vorrang)
    behalten, verworfen = deduplizieren([*(_aus_json(f) for f in bestand), *neue_eigene, *neue])
    ids_bestand = {f["id"] for f in bestand}
    ergebnis = [f for f in behalten if f.id not in ids_bestand and f.quelle_typ == "wikipedia"]
    eigen = [f for f in ergebnis if f.meta.get("eigen")]
    for f, grund in verworfen:
        if f.id not in ids_bestand:
            ktx.protokoll.verwerfen(ktx.kategorie, "dedupe", grund,
                                    {"frage": f.frage, "richtig": f.richtig, "titel": f.quelle_titel})
    return eigen + [f for f in ergebnis if not f.meta.get("eigen")][:bedarf], neu_verarbeitet, verbrauch


def _eigene(ktx: Kontext, titel: list[str], verarbeitet: dict[str, dict], pro_quelle: dict[str, list[dict]],
            aufloesen: Callable) -> list:
    """Eigene Artikel der Kategorie, die noch nicht als eigene verarbeitet wurden (Titel oder QID) und weniger
    als 2 Fragen haben. Ein früher automatisch verarbeiteter Artikel (z. B. wegen Bekanntheit < 3 ohne Fragen)
    kommt einmal erneut dran. Nicht auffindbare Titel werden gemeldet."""
    if not titel:
        return []
    kandidaten, fehler = aufloesen(ktx.http, titel)
    for t, grund in fehler:
        log.warning("%s: eigener Artikel „%s“ übersprungen: %s", ktx.kategorie, t, grund)
        ktx.protokoll.verwerfen(ktx.kategorie, "eigene", grund, {"titel": t})
    erledigt = {d.get("qid") for d in verarbeitet.values() if d.get("eigen")}
    offen = [k for k in kandidaten if k.qid not in erledigt and len(pro_quelle.get(k.qid, [])) < 2]
    log.info("%s: %d eigene Artikel in der Liste, %d noch nicht verarbeitet", ktx.kategorie, len(titel), len(offen))
    return offen


def _automatische_auswahl(ktx: Kontext, verarbeitet: dict[str, dict], ausser: set[str]
                          ) -> tuple[list, list, dict[str, float]]:
    """Kandidaten aus Startkategorien und Qualitätsartikeln nach Bekanntheitsfilter und Kategorie-Abgleich.
    `ausser`: QIDs, die schon als eigene Artikel kommen. Gibt (Kandidaten, alle Rohkandidaten für den
    Themenausgleich, Seitenaufruf-Schwelle pro Sprache) zurück."""
    from .config import EN_SCHWELLEN
    from .popularity import Bekanntheit
    from .wikipedia.kandidaten import passende_kategorie, sammeln, sammeln_englisch

    roh = sammeln(ktx.http, ktx.kategorie, ktx.schwellen.min_sitelinks)
    kandidaten = ktx.filtern([k for k in roh if k.schluessel not in verarbeitet and k.qid not in ausser],
                             "artikel")
    kandidaten, falsche_kategorie = passende_kategorie(ktx.http, kandidaten, ktx.kategorie)
    for k, grund in falsche_kategorie:
        ktx.protokoll.verwerfen(ktx.kategorie, "kategorie", grund, {"titel": k.titel})
    if falsche_kategorie:
        log.info("%s: %d Artikel passen thematisch zu einer anderen Kategorie, z. B. %s",
                 ktx.kategorie, len(falsche_kategorie),
                 ", ".join(f"{k.titel} ({g.split(': ')[1]})" for k, g in falsche_kategorie[:5]))
    schwelle = {"de": ktx.schwellen.min_pageviews}
    alle_roh = list(roh)  # für den Themenausgleich (Startkategorie pro Artikel)
    en_schwellen = EN_SCHWELLEN.get(ktx.kategorie)
    if en_schwellen:
        # Ergänzend englische Artikel, wenn kein deutscher Artikel zum selben Thema den Bekanntheitsfilter
        # besteht (fehlt oder wird auf de.wikipedia kaum aufgerufen, z. B. Darth Vader). Eigene Schwellen.
        schwelle["en"] = en_schwellen.min_pageviews
        de_qids = {k.qid for k in kandidaten} | {d.get("qid") for d in verarbeitet.values()} | ausser
        en_alle = sammeln_englisch(ktx.http, ktx.kategorie, en_schwellen.min_sitelinks)
        alle_roh += en_alle
        en_roh = [k for k in en_alle if k.qid not in de_qids and k.schluessel not in verarbeitet]
        en_bekanntheit = Bekanntheit(ktx.http, heute=ktx.bekanntheit.heute, exakt=ktx.bekanntheit.exakt,
                                     sprache="en")
        kandidaten += ktx.filtern(en_roh, "artikel-en", bekanntheit=en_bekanntheit, schwellen=en_schwellen)
    return kandidaten, alle_roh, schwelle


def _themen_ausgleichen(ktx: Kontext, roh: list, kandidaten: list, bestand: list[dict]) -> list:
    """Kandidaten reihum nach Thema ordnen (siehe wikipedia/themen.py), Bestand eingerechnet."""
    from collections import Counter

    from .wikipedia.kandidaten import artikel_kategorien
    from .wikipedia.themen import ausgleichen, thema

    # Schlüssel „Titel“ bzw. „en:Titel“; Wikipedia-Kategorien gibt es nur für deutsche Artikel,
    # englische Artikel ordnet thema() über ihre Startkategorie („en:Category:…“) ein.
    quelle = {k.schluessel: k.extra.get("quelle") for k in roh}
    datum = {k.schluessel: k.datum.year for k in roh if k.datum}

    def schluessel_bestand(f: dict) -> str:
        en = f.get("quelle_url", "").startswith("https://en.wikipedia.org/")
        return f"en:{f['quelle_titel']}" if en else f["quelle_titel"]

    alt = [f for f in bestand if f["quelle_typ"] == "wikipedia" and f.get("quelle_titel")]
    titel_de = {k.titel for k in kandidaten if k.sprache == "de"}
    titel_de |= {s for s in map(schluessel_bestand, alt) if not s.startswith("en:")}
    kats = artikel_kategorien(ktx.http, sorted(titel_de))

    def thema_von(schluessel: str) -> str:
        return thema(ktx.kategorie, kats.get(schluessel, []), quelle.get(schluessel), datum.get(schluessel))

    zaehler = Counter(thema_von(schluessel_bestand(f)) for f in alt)
    geordnet = ausgleichen(kandidaten, lambda k: thema_von(k.schluessel), zaehler)
    neu = Counter(thema_von(k.schluessel) for k in kandidaten)
    log.info("%s: Fragen pro Thema im Bestand: %s; neue Kandidaten: %s", ktx.kategorie,
             dict(zaehler.most_common()), dict(neu.most_common()))
    return geordnet


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
