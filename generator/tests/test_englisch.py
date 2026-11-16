"""Englische Wikipedia als ergänzende Quelle (zuerst nur für Star Wars)."""
import random

from wikiquiz_gen.config import EN_SCHWELLEN, KATEGORIEN
from wikiquiz_gen.llm.fragen import artikel_verarbeiten
from wikiquiz_gen.popularity import Kandidat, api_url
from wikiquiz_gen.sparql import artikel_url
from wikiquiz_gen.wikipedia import kandidaten as kand
from wikiquiz_gen.wikipedia.auszug import auszug
from wikiquiz_gen.wikipedia.quellen import EN_STARTKATEGORIEN

TEXT_EN = (
    "Darth Vader is a fictional character in the Star Wars franchise. He was originally a Jedi "
    "named Anakin Skywalker who fell to the dark side of the Force. He is the father of Luke Skywalker "
    "and Princess Leia."
)


class FakeLLM:
    def __init__(self, *antworten):
        self.antworten = list(antworten)

    def json(self, nachricht, schema, system=None, max_tokens=16000):
        return self.antworten.pop(0)


def test_englische_quelle_nur_fuer_themenkategorien_mit_figuren():
    assert set(EN_SCHWELLEN) == {"starwars", "harrypotter"} == set(EN_STARTKATEGORIEN)
    assert set(EN_SCHWELLEN) <= set(KATEGORIEN)


def test_urls_und_schluessel():
    assert api_url("en") == "https://en.wikipedia.org/w/api.php"
    assert artikel_url("Darth Vader", "en") == "https://en.wikipedia.org/wiki/Darth_Vader"
    assert artikel_url("Köln") == "https://de.wikipedia.org/wiki/K%C3%B6ln"
    assert Kandidat("Q1", "Jedi", "Jedi", 60).schluessel == "Jedi"
    assert Kandidat("Q2", "Jedi", "Jedi", 60, sprache="en").schluessel == "en:Jedi"


def test_deutsche_frage_aus_englischem_text():
    gen = FakeLLM({"bekanntheit_thema": 5, "fragen": [{
        "frage": "Wie hiess Darth Vader, bevor er der dunklen Seite verfiel?",
        "richtige_antwort": "Anakin Skywalker",
        "falsche_antworten": ["Obi-Wan Kenobi", "Han Solo", "Lando Calrissian"],
        "schwierigkeit": 1,
        "belegstelle": "originally a Jedi named Anakin Skywalker",
        "begruendung_bekanntheit": "Zentrale Figur der Filmreihe.",
    }]})
    pruefer = FakeLLM({"deine_antwort": "Anakin Skywalker", "eindeutig": True, "allgemeinwissen": 4, "probleme": []})
    erg = artikel_verarbeiten(gen, pruefer, "starwars", "Darth Vader", "Q12206942", TEXT_EN, [],
                              rng=random.Random(1), sprache="en")
    assert len(erg.angenommen) == 1
    f = erg.angenommen[0].to_json()
    assert f["quelle_url"] == "https://en.wikipedia.org/wiki/Darth_Vader"
    assert f["lizenz"] == "CC BY-SA 4.0" and f["id"].startswith("wp-")


def test_englische_nebenabschnitte_uebersprungen():
    voll = "Intro sentence.\n\n== Biography ==\nPart one.\n\n== References ==\nRef X.\n\n== External links ==\nLink."
    a = auszug(voll)
    assert "Part one." in a and "Ref X" not in a and "Link." not in a


def test_sammeln_englisch(monkeypatch):
    seiten = [
        {"title": "Darth Vader", "ns": 0, "pageprops": {"wikibase_item": "Q1"}},
        {"title": "Minor droid", "ns": 0, "pageprops": {"wikibase_item": "Q3"}},   # zu wenige Sitelinks
        {"title": "Vader (redirect)", "ns": 0, "pageprops": {}},                   # ohne QID
    ]
    sprachen = []
    monkeypatch.setattr(kand, "kategorie_artikel",
                        lambda http, kat, tiefe, max_artikel, sprache: sprachen.append(sprache) or seiten)
    monkeypatch.setattr(kand, "sitelinks", lambda http, qids: {"Q1": 80, "Q3": 5})
    monkeypatch.setattr(kand, "ereignisdaten", lambda http, qids: {})
    ks = kand.sammeln_englisch(None, "starwars", min_sitelinks=20)
    assert [(k.titel, k.sprache, k.schluessel) for k in ks] == [("Darth Vader", "en", "en:Darth Vader")]
    assert set(sprachen) == {"en"}


def test_themen_ausgleichen_mit_englischen_kandidaten(monkeypatch):
    from types import SimpleNamespace

    from wikiquiz_gen import pipeline

    abgefragt = []
    monkeypatch.setattr(kand, "artikel_kategorien", lambda http, titel: abgefragt.extend(titel) or {})
    de = Kandidat("Q1", "Jedi", "Jedi", 60, pageviews=60)
    de.extra["quelle"] = "Kategorie:Star Wars"
    en1 = Kandidat("Q2", "Yoda", "Yoda", 68, pageviews=500, sprache="en")
    en1.extra["quelle"] = "en:Category:Star Wars characters"
    en2 = Kandidat("Q3", "Grogu", "Grogu", 31, pageviews=1300, sprache="en")
    en2.extra["quelle"] = "en:Category:Star Wars characters"
    # Bestand: schon eine Frage aus einer englischen Figur → Figuren kommen nach dem deutschen Thema
    bestand = [{"quelle_typ": "wikipedia", "quelle_titel": "Darth Vader",
                "quelle_url": "https://en.wikipedia.org/wiki/Darth_Vader"}]
    alle = [de, en1, en2, Kandidat("Q4", "Darth Vader", "Darth Vader", 85, sprache="en",
                                   extra={"quelle": "en:Category:Star Wars characters"})]
    ktx = SimpleNamespace(kategorie="starwars", http=None)
    geordnet = pipeline._themen_ausgleichen(ktx, alle, [en2, en1, de], bestand)
    assert geordnet[0] is de
    assert abgefragt == ["Jedi"]  # nur deutsche Titel nach Wikipedia-Kategorien gefragt
