"""Eigene Artikel pro Kategorie (eigene_artikel.toml): Nischenwissen ohne Bekanntheitsfilter."""
import random
from datetime import date

import pytest

from wikiquiz_gen import pipeline
from wikiquiz_gen.config import EIGENE_ARTIKEL_DATEI, KATEGORIEN, lade_eigene_artikel
from wikiquiz_gen.llm.fragen import artikel_verarbeiten
from wikiquiz_gen.llm.prompts import GENERIERUNG_ZUSATZ_EIGEN
from wikiquiz_gen.output import Protokoll
from wikiquiz_gen.popularity import Bekanntheit, Kandidat
from wikiquiz_gen.sparql import ENDPOINT
from wikiquiz_gen.templates.base import Kontext
from wikiquiz_gen.config import Schwellen
from wikiquiz_gen.wikipedia.kandidaten import eigene_kandidaten

TEXT = (
    "Der Zibelemärit ist ein traditioneller Volksmarkt in der Stadt Bern. Er findet jeweils am vierten "
    "Montag im November statt. Angeboten werden vor allem Zwiebeln, die zu Zöpfen geflochten werden. "
) * 5


class FakeLLM:
    def __init__(self, *antworten):
        self.antworten = list(antworten)
        self.aufrufe = []
        self.modell = "fake"

    def json(self, nachricht, schema, system=None, max_tokens=16000):
        self.aufrufe.append(nachricht)
        return self.antworten.pop(0)

    def pruefe_anmeldung(self):
        pass


def gen_antwort(bekanntheit=2):
    return {"bekanntheit_thema": bekanntheit, "fragen": [{
        "frage": "Was wird am Berner Zibelemärit vor allem verkauft?",
        "richtige_antwort": "Zwiebeln",
        "falsche_antworten": ["Kürbisse", "Äpfel", "Kastanien"],
        "schwierigkeit": 2,
        "belegstelle": "Angeboten werden vor allem Zwiebeln",
        "begruendung_bekanntheit": "Bekannter Markt in Bern.",
    }]}


def pruef_antwort(allgemeinwissen=1):
    return {"deine_antwort": "Zwiebeln", "eindeutig": True, "allgemeinwissen": allgemeinwissen, "probleme": []}


# ---- Konfigurationsdatei ---------------------------------------------------------
def test_datei_im_repository_ist_gueltig():
    assert EIGENE_ARTIKEL_DATEI.exists()
    assert set(lade_eigene_artikel()) <= set(KATEGORIEN)


def test_laden(tmp_path):
    pfad = tmp_path / "eigene.toml"
    pfad.write_text('schweiz = ["Zibelemärit", " Chesslete ", "Zibelemärit", ""]\nkunst = []\n'
                    'starwars = ["en:Grogu"]\n', encoding="utf-8")
    assert lade_eigene_artikel(pfad) == {"schweiz": ["Zibelemärit", "Chesslete"], "starwars": ["en:Grogu"]}
    assert lade_eigene_artikel(tmp_path / "fehlt.toml") == {}


@pytest.mark.parametrize("inhalt", ['schwiez = ["Bern"]', 'schweiz = "Bern"', "schweiz = [1]"])
def test_laden_fehler(tmp_path, inhalt):
    pfad = tmp_path / "eigene.toml"
    pfad.write_text(inhalt, encoding="utf-8")
    with pytest.raises(ValueError):
        lade_eigene_artikel(pfad)


# ---- Titel auflösen --------------------------------------------------------------
class FakeHttp:
    """Beantwortet die MediaWiki-Abfrage von eigene_kandidaten() und die Sitelink-Abfrage (SPARQL)."""

    def __init__(self):
        self.urls = []

    def json(self, url, params=None, daten=None, ttl=None):
        self.urls.append(url)
        if url == ENDPOINT:
            return {"results": {"bindings": [
                {"item": {"value": "http://www.wikidata.org/entity/Q1"}, "sl": {"value": "7"}},
            ]}}
        if url.startswith("https://en."):
            return {"query": {"pages": [{"title": "Grogu", "pageprops": {"wikibase_item": "Q3"}}]}}
        return {"query": {
            "normalized": [{"from": "zibelemärit", "to": "Zibelemärit"}],
            "redirects": [{"from": "Zibelemärit", "to": "Zibelemärit (Bern)"},
                          {"from": "Zwiebelmarkt Bern", "to": "Zibelemärit (Bern)"}],
            "pages": [
                {"title": "Zibelemärit (Bern)", "pageprops": {"wikibase_item": "Q1"}},
                {"title": "Gibtsnicht", "missing": True},
                {"title": "Märit", "pageprops": {"wikibase_item": "Q2", "disambiguation": ""}},
            ],
        }}


def test_eigene_kandidaten():
    http = FakeHttp()
    kandidaten, fehler = eigene_kandidaten(
        http, ["zibelemärit", "Gibtsnicht", "Märit", "Zwiebelmarkt Bern", "en:Grogu"])
    # Weiterleitung aufgelöst, doppelter Eintrag (zweite Weiterleitung) nur einmal
    assert [(k.schluessel, k.qid) for k in kandidaten] == [("Zibelemärit (Bern)", "Q1"), ("en:Grogu", "Q3")]
    assert kandidaten[0].sitelinks == 7 and kandidaten[0].pageviews is None
    assert all(k.extra["eigen"] and k.extra["quelle"] == "eigene Liste" for k in kandidaten)
    assert sorted(fehler) == [("Gibtsnicht", "artikel fehlt"), ("Märit", "begriffsklaerung")]
    assert any(u.startswith("https://en.wikipedia.org/") for u in http.urls)


# ---- LLM-Schwellen ---------------------------------------------------------------
def test_eigene_ohne_bekanntheitsschwellen():
    gen, pruefer = FakeLLM(gen_antwort(bekanntheit=2)), FakeLLM(pruef_antwort(allgemeinwissen=1))
    erg = artikel_verarbeiten(gen, pruefer, "schweiz", "Zibelemärit", "Q1", TEXT, [],
                              rng=random.Random(1), eigen=True)
    assert len(erg.angenommen) == 1
    assert gen.aufrufe[0].endswith("\n\n" + GENERIERUNG_ZUSATZ_EIGEN)
    assert GENERIERUNG_ZUSATZ_EIGEN not in pruefer.aufrufe[0]


def test_ohne_eigen_gelten_schwellen():
    gen, pruefer = FakeLLM(gen_antwort(bekanntheit=2)), FakeLLM()
    erg = artikel_verarbeiten(gen, pruefer, "schweiz", "Zibelemärit", "Q1", TEXT, [], rng=random.Random(1))
    assert not erg.angenommen and "bekanntheit_thema" in erg.verworfen[0][1]
    assert GENERIERUNG_ZUSATZ_EIGEN not in gen.aufrufe[0]


def test_eigene_pruefer_muss_trotzdem_zustimmen():
    falsch = {**pruef_antwort(), "deine_antwort": "Kürbisse"}
    erg = artikel_verarbeiten(FakeLLM(gen_antwort()), FakeLLM(falsch), "schweiz", "Zibelemärit", "Q1", TEXT, [],
                              rng=random.Random(1), eigen=True)
    assert not erg.angenommen and "pruefer" in erg.verworfen[0][1]


# ---- Pipeline --------------------------------------------------------------------
@pytest.fixture
def umgebung(monkeypatch):
    """Pipeline ohne Netz: eigene Liste, Titelauflösung, Artikeltext und LLM ersetzt."""
    from wikiquiz_gen import config
    from wikiquiz_gen.llm import client
    from wikiquiz_gen.wikipedia import auszug, kandidaten

    llm = {"gen": FakeLLM(gen_antwort()), "pruefer": FakeLLM(pruef_antwort())}
    monkeypatch.setattr(config, "lade_eigene_artikel",
                        lambda: {"schweiz": ["Zibelemärit", "Chesslete"]})

    def aufloesen(http, titel):
        return [_kandidat(t, f"Q{i}") for i, t in enumerate(titel, 1)], []

    def _kandidat(titel, qid):
        k = Kandidat(qid=qid, label=titel, titel=titel, sitelinks=3)
        k.extra.update({"quelle": "eigene Liste", "eigen": True})
        return k

    monkeypatch.setattr(kandidaten, "eigene_kandidaten", aufloesen)
    monkeypatch.setattr(kandidaten, "amtierende", lambda http, qids: set())
    monkeypatch.setattr(auszug, "klartext", lambda http, titel, sprache="de": TEXT)
    monkeypatch.setattr(client.LLM, "generierung", staticmethod(lambda v: llm["gen"]))
    monkeypatch.setattr(client.LLM, "pruefung", staticmethod(lambda v: llm["pruefer"]))

    def automatisch(*args):
        raise AssertionError("automatische Auswahl darf bei erreichtem Ziel nicht laufen")

    monkeypatch.setattr(pipeline, "_automatische_auswahl", automatisch)
    ktx = Kontext("schweiz", None, Bekanntheit(None, heute=date(2026, 1, 1)), Schwellen(),
                  Protokoll(aktiv=False))
    return ktx, llm


def test_pipeline_eigene_auch_bei_erreichtem_ziel(umgebung):
    ktx, llm = umgebung
    # Chesslete wurde schon als eigener Artikel verarbeitet, Zibelemärit nur automatisch (ohne Fragen)
    verarbeitet = {"Zibelemärit": {"qid": "Q1", "grund": "bekanntheit"}, "Chesslete": {"qid": "Q2", "eigen": True}}
    fragen, neu, _ = pipeline.wikipedia(ktx, ziel=0, max_artikel=5, bestand=[], verarbeitet=verarbeitet,
                                        threads=1)
    assert [f.quelle_titel for f in fragen] == ["Zibelemärit"]
    assert neu["Zibelemärit"]["eigen"] is True
    assert len(llm["gen"].aufrufe) == 1


def test_pipeline_ohne_offene_eigene_kein_llm(umgebung):
    ktx, llm = umgebung
    verarbeitet = {t: {"qid": q, "eigen": True} for t, q in (("Zibelemärit", "Q1"), ("Chesslete", "Q2"))}
    assert pipeline.wikipedia(ktx, ziel=0, max_artikel=5, bestand=[], verarbeitet=verarbeitet) == ([], {}, None)
    assert not llm["gen"].aufrufe
