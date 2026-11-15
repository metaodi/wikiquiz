"""Bekanntheitsfilter: Sitelinks, Seitenaufrufe, Ausschlüsse (Listen, BKL, Stubs, junge Ereignisse).

Reihenfolge von günstig nach teuer, damit möglichst wenige Requests nötig sind.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from urllib.parse import quote

from .config import Schwellen
from .http import TAG, Http

log = logging.getLogger(__name__)

PAGEVIEWS_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "de.wikipedia/all-access/user/{titel}/monthly/{start}/{ende}"
)
API_URL = "https://de.wikipedia.org/w/api.php"
# Klartext ≈ 60 % des Wikitexts (Markup, Vorlagen, Einzelnachweise). Volltexte über TextExtracts
# werden stark gedrosselt; für den Stub-Filter genügt die Länge aus prop=info (50 Titel/Request).
KLARTEXT_ANTEIL = 0.6
# Vorfilter mit 60-Tage-Werten (50 Titel pro Request). Nur Werte im Graubereich
# [unten × Schwelle, oben × Schwelle] werden über 12 Monate (REST-API, 1 Titel/Request) verfeinert.
GRAUBEREICH = (0.5, 2.0)


@dataclass
class Kandidat:
    qid: str
    label: str
    titel: str  # Titel des de.wikipedia-Artikels
    sitelinks: int
    datum: date | None = None  # Ereignisdatum (P585/P580), falls vorhanden
    pageviews: float | None = None
    zeichen: int | None = None
    extra: dict = field(default_factory=dict)


def zeitraum_12_monate(heute: date) -> tuple[date, date]:
    """Die letzten 12 vollständigen Monate vor `heute`."""
    ende = heute.replace(day=1) - timedelta(days=1)
    jahr, monat = ende.year - 1, ende.month + 1
    if monat == 13:
        jahr, monat = jahr + 1, 1
    return date(jahr, monat, 1), ende


def ist_listentitel(titel: str) -> bool:
    return titel.startswith("Liste ") or titel.startswith("Listen ")


class Bekanntheit:
    def __init__(self, http: Http, heute: date | None = None, exakt: bool = False) -> None:
        self.http = http
        self.exakt = exakt  # immer 12-Monats-Werte abfragen
        self.heute = heute or date.today()
        self._start, self._ende = zeitraum_12_monate(self.heute)

    # ---- einzelne Kennzahlen -------------------------------------------------
    def pageviews(self, titel: str) -> float:
        """Durchschnittliche Seitenaufrufe pro Tag (nur Menschen) über 12 Monate."""
        url = PAGEVIEWS_URL.format(
            titel=quote(titel.replace(" ", "_"), safe=""),
            start=self._start.strftime("%Y%m%d00"),
            ende=self._ende.strftime("%Y%m%d00"),
        )
        res = self.http.json(url, ttl=30 * TAG)
        if not res:
            return 0.0
        summe = sum(item["views"] for item in res.get("items", []))
        tage = (self._ende - self._start).days + 1
        return summe / tage

    def pageviews_60_tage(self, titel_liste: list[str]) -> dict[str, float]:
        """Durchschnitt pro Tag über die letzten 60 Tage, 50 Titel pro Request (PageViewInfo)."""
        werte: dict[str, float] = {}
        for i in range(0, len(titel_liste), 50):
            block = titel_liste[i : i + 50]
            fortsetzung: dict = {}
            while True:
                res = self.http.json(
                    API_URL,
                    params={"action": "query", "format": "json", "formatversion": "2",
                            "prop": "pageviews", "pvipdays": "60", "titles": "|".join(block),
                            **fortsetzung},
                    ttl=14 * TAG,
                )
                q = res.get("query", {})
                norm = {n["to"]: n["from"] for n in q.get("normalized", [])}
                for p in q.get("pages", []):
                    if "pageviews" not in p:
                        continue  # kommt in einer späteren Fortsetzung
                    tage = [v for v in p["pageviews"].values() if v is not None]
                    werte[norm.get(p["title"], p["title"])] = sum(tage) / len(tage) if tage else 0.0
                if "continue" not in res:
                    break
                fortsetzung = res["continue"]
        return werte

    def seiteninfo(self, titel_liste: list[str]) -> dict[str, dict]:
        """Begriffsklärung/fehlend für bis zu 50 Titel pro Request."""
        info: dict[str, dict] = {}
        for i in range(0, len(titel_liste), 50):
            block = titel_liste[i : i + 50]
            res = self.http.json(
                API_URL,
                params={
                    "action": "query",
                    "format": "json",
                    "formatversion": "2",
                    "prop": "pageprops|info",
                    "ppprop": "disambiguation",
                    "titles": "|".join(block),
                },
                ttl=30 * TAG,
            )
            q = res.get("query", {})
            norm = {n["to"]: n["from"] for n in q.get("normalized", [])}
            for p in q.get("pages", []):
                original = norm.get(p["title"], p["title"])
                info[original] = {
                    "fehlt": p.get("missing", False),
                    "bkl": "disambiguation" in p.get("pageprops", {}),
                    "bytes": p.get("length", 0),
                }
        return info

    def klartext(self, titel: str, nur_einleitung: bool = False) -> str:
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "extracts",
            "explaintext": "1",
            "exsectionformat": "plain",
            "redirects": "1",
            "titles": titel,
        }
        if nur_einleitung:
            params["exintro"] = "1"
        res = self.http.json(API_URL, params=params, ttl=30 * TAG)
        seiten = res.get("query", {}).get("pages", [])
        return seiten[0].get("extract", "") if seiten else ""

    # ---- Filter ------------------------------------------------------------------
    def filtern(
        self, kandidaten: list[Kandidat], schwellen: Schwellen
    ) -> tuple[list[Kandidat], list[tuple[Kandidat, str]]]:
        """Gibt (bestanden, [(abgelehnt, grund)]) zurück."""
        abgelehnt: list[tuple[Kandidat, str]] = []
        rest: list[Kandidat] = []

        for k in kandidaten:
            if k.sitelinks < schwellen.min_sitelinks:
                abgelehnt.append((k, f"sitelinks {k.sitelinks} < {schwellen.min_sitelinks}"))
            elif ist_listentitel(k.titel):
                abgelehnt.append((k, "liste"))
            elif k.datum and (self.heute - k.datum).days < schwellen.min_ereignis_alter_tage:
                abgelehnt.append((k, f"ereignis zu jung ({k.datum.isoformat()})"))
            else:
                rest.append(k)

        # Erst 60-Tage-Werte im Block, dann 12 Monate (seriell, REST drosselt) nur im Graubereich
        schnell = self.pageviews_60_tage([k.titel for k in rest])
        unten, oben = (g * schwellen.min_pageviews for g in GRAUBEREICH)
        for k in rest:
            pv60 = schnell.get(k.titel, 0.0)
            k.extra["pageviews_60"] = pv60
            if self.exakt or unten <= pv60 <= oben:
                k.pageviews = self.pageviews(k.titel)
            else:
                k.pageviews = pv60
        neu = []
        for k in rest:
            if k.pageviews < schwellen.min_pageviews:
                abgelehnt.append((k, f"pageviews {k.pageviews:.0f} < {schwellen.min_pageviews:.0f}"))
            else:
                neu.append(k)
        rest = neu

        info = self.seiteninfo([k.titel for k in rest])
        neu = []
        for k in rest:
            i = info.get(k.titel, {})
            if i.get("fehlt"):
                abgelehnt.append((k, "artikel fehlt"))
            elif i.get("bkl"):
                abgelehnt.append((k, "begriffsklaerung"))
            elif i.get("bytes", 0) < schwellen.min_zeichen / KLARTEXT_ANTEIL:
                k.zeichen = int(i.get("bytes", 0) * KLARTEXT_ANTEIL)
                abgelehnt.append((k, f"stub (~{k.zeichen} zeichen, {i.get('bytes', 0)} bytes wikitext)"))
            else:
                k.zeichen = int(i.get("bytes", 0) * KLARTEXT_ANTEIL)
                neu.append(k)
        bestanden = neu
        log.info("Bekanntheitsfilter: %d bestanden, %d abgelehnt", len(bestanden), len(abgelehnt))
        return bestanden, abgelehnt
