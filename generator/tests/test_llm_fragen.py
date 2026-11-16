import random
import pytest

from wikiquiz_gen.llm.fragen import artikel_verarbeiten, beleg_vorhanden, zuordnen_antwort
from wikiquiz_gen.wikipedia.auszug import auszug
from wikiquiz_gen.wikipedia.quellen import zuordnen

TEXT = (
    "Die Zauberflöte ist eine Oper in zwei Aufzügen von Wolfgang Amadeus Mozart. "
    "Das Libretto stammt von Emanuel Schikaneder. Die Uraufführung fand am 30. September 1791 "
    "im Freihaustheater in Wien statt. Sie gehört zu den bekanntesten Werken der Gattung „Oper“."
)


class FakeLLM:
    def __init__(self, *antworten):
        self.antworten = list(antworten)
        self.aufrufe = []

    def json(self, nachricht, schema, system=None, max_tokens=16000):
        self.aufrufe.append(nachricht)
        return self.antworten.pop(0)


def gen_antwort(bekanntheit=5, **frage):
    basis = {
        "frage": "Welcher Komponist schrieb die Oper ‚Die Zauberflöte‘?",
        "richtige_antwort": "Mozart",
        "falsche_antworten": ["Beethoven", "Haydn", "Schubert"],
        "schwierigkeit": 1,
        "belegstelle": "eine Oper in zwei Aufzügen von Wolfgang Amadeus Mozart",
        "begruendung_bekanntheit": "Weltbekannte Oper.",
    }
    basis.update(frage)
    return {"bekanntheit_thema": bekanntheit, "fragen": [basis]}


def pruef_antwort(antwort="Mozart", eindeutig=True, allgemeinwissen=5):
    return {"deine_antwort": antwort, "eindeutig": eindeutig, "allgemeinwissen": allgemeinwissen, "probleme": []}


def verarbeiten(gen, pruefer):
    return artikel_verarbeiten(gen, pruefer, "kunst", "Die Zauberflöte", "Q12", TEXT, [], rng=random.Random(1))


def test_beleg_vorhanden():
    assert beleg_vorhanden("Das Libretto stammt von Emanuel Schikaneder.", TEXT)
    assert beleg_vorhanden("Die Uraufführung fand … im Freihaustheater in Wien statt", TEXT)
    assert beleg_vorhanden('Werken der Gattung "Oper"', TEXT)  # Anführungszeichen normalisiert
    assert not beleg_vorhanden("Das Libretto stammt von Mozart selbst", TEXT)
    assert not beleg_vorhanden("Oper", TEXT)  # zu kurz


def test_beleg_ss_und_eszett():
    assert beleg_vorhanden("die Strasse ist gross und breit", "Die Straße ist groß und breit.")


def test_zuordnen_antwort():
    optionen = ["Haydn", "Mozart", "Beethoven", "Schubert"]
    assert zuordnen_antwort("Mozart", optionen) == 1
    assert zuordnen_antwort("Wolfgang Amadeus Mozart", optionen) == 1
    assert zuordnen_antwort("Bach", optionen) is None


def test_angenommen():
    gen, pruefer = FakeLLM(gen_antwort()), FakeLLM(pruef_antwort())
    erg = verarbeiten(gen, pruefer)
    assert len(erg.angenommen) == 1
    f = erg.angenommen[0]
    assert f.quelle_typ == "wikipedia" and f.quelle_id == "Q12"
    assert f.to_json()["lizenz"] == "CC BY-SA 4.0"
    # Prüfer sieht die Antworten gemischt und erfährt nicht, welche richtig ist
    prompt = pruefer.aufrufe[0]
    assert "richtig" not in prompt.lower().split("antworten (gemischt)")[1].split("artikelauszug")[0]
    assert all(a in prompt for a in ["Mozart", "Beethoven", "Haydn", "Schubert"])


def test_verworfen_bekanntheit():
    erg = verarbeiten(FakeLLM(gen_antwort(bekanntheit=2)), FakeLLM())
    assert not erg.angenommen and "bekanntheit_thema" in erg.verworfen[0][1]


def test_verworfen_beleg_ohne_pruefaufruf():
    pruefer = FakeLLM()
    erg = verarbeiten(FakeLLM(gen_antwort(belegstelle="Mozart schrieb sie im Jahr 1791 allein")), pruefer)
    assert "belegstelle" in erg.verworfen[0][1]
    assert pruefer.aufrufe == []  # keine Kosten für die Prüfung


def test_verworfen_pruefer_anders():
    erg = verarbeiten(FakeLLM(gen_antwort()), FakeLLM(pruef_antwort("Haydn")))
    assert "pruefer antwortet anders" in erg.verworfen[0][1]


def test_verworfen_nicht_eindeutig_und_allgemeinwissen():
    assert "nicht eindeutig" in verarbeiten(FakeLLM(gen_antwort()), FakeLLM(pruef_antwort(eindeutig=False))).verworfen[0][1]
    assert "allgemeinwissen" in verarbeiten(FakeLLM(gen_antwort()), FakeLLM(pruef_antwort(allgemeinwissen=2))).verworfen[0][1]


def test_verworfen_formal():
    erg = verarbeiten(FakeLLM(gen_antwort(falsche_antworten=["Haydn", "Haydn", "Bach"])), FakeLLM())
    assert erg.verworfen[0][1].startswith("formal")


def test_auszug_ueberspringt_nebenabschnitte():
    voll = "Einleitung.\n\n== Leben ==\nAbsatz eins.\n\n== Literatur ==\nBuch X.\n\n== Werk ==\nAbsatz zwei."
    a = auszug(voll)
    assert "Buch X" not in a and "Absatz zwei." in a and a.startswith("Einleitung.")
    assert len(auszug("Satz. " * 2000)) <= 4000


def test_zuordnung_qualitaetsartikel():
    assert zuordnen(["Kategorie:Oper (Werk)", "Kategorie:Werk von Wolfgang Amadeus Mozart"]) == "kunst"
    assert zuordnen(["Kategorie:Schlacht des Zweiten Weltkriegs"]) == "geschichte"
    assert zuordnen(["Kategorie:Mann", "Kategorie:Geboren 1900"]) is None


def test_zuordnung_nur_am_wortanfang():
    # „Verdichter“ und „Kirchenlieddichter“ sind keine Dichter
    assert zuordnen(["Kategorie:Verdichter", "Kategorie:Leistungssteigerung (Verbrennungsmotor)",
                     "Kategorie:Technikgeschichte (20. Jahrhundert)"]) == "naturwissenschaften"
    assert zuordnen(["Kategorie:Kirchenlieddichter", "Kategorie:Hingerichtete Person (NS-Opfer)",
                     "Kategorie:Häftling im KZ Buchenwald"]) == "geschichte"


def test_zuordnung_mit_berufen():
    # Kepler: Astronom (Q11063) und Mathematiker (Q170790), daneben Schriftsteller (Q36180)
    kats = ["Kategorie:Autor", "Kategorie:Erzählung", "Kategorie:Literatur (17. Jahrhundert)"]
    assert zuordnen(kats, ["Q11063", "Q170790", "Q36180"]) == "naturwissenschaften"
    # Komponist (Q36834) bleibt Kunst
    assert zuordnen(["Kategorie:Komponist (Klassik)"], ["Q36834", "Q486748"]) == "kunst"


def test_zuordnung_personen():
    assert zuordnen(["Kategorie:Politiker (21. Jahrhundert)", "Kategorie:Literatur (Deutsch)", "Kategorie:Autor"]) == "geschichte"
    assert zuordnen(["Kategorie:Philosoph (18. Jahrhundert)", "Kategorie:Literatur (18. Jahrhundert)"]) == "allgemeinwissen"
    assert zuordnen(["Kategorie:Komponist (Klassik)", "Kategorie:Literatur (Deutsch)"]) == "kunst"
    assert zuordnen(["Kategorie:Person im Zweiten Weltkrieg", "Kategorie:Schlacht"]) == "geschichte"


def test_leere_umgebungsvariable_zaehlt_als_nicht_gesetzt(monkeypatch):
    from wikiquiz_gen.llm import client

    monkeypatch.setenv("WIKIQUIZ_GEN_MODEL", "")
    monkeypatch.setenv("WIKIQUIZ_CHECK_MODEL", "claude-sonnet-5-5")
    monkeypatch.setenv("WIKIQUIZ_EFFORT", " ")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    v = client.Verbrauch()
    assert client.LLM.generierung(v).modell == client.STANDARD_MODELL
    assert client.LLM.pruefung(v).modell == "claude-sonnet-5-5"
    assert client.LLM.generierung(v).effort == "medium"
    monkeypatch.setenv("WIKIQUIZ_CHECK_MODEL", "")
    assert client.LLM.pruefung(v).modell == client.STANDARD_MODELL


def test_generierung_und_pruefung_teilen_einen_client(monkeypatch):
    """Ein Client = ein Token-Austausch; OIDC-Tokens sind nur einmal eintauschbar."""
    from wikiquiz_gen.llm import client

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("WIKIQUIZ_CHECK_MODEL", "claude-sonnet-5-5")
    v = client.Verbrauch()
    assert client.LLM.generierung(v).client is client.LLM.pruefung(v).client


def test_kategorie_abgleich(monkeypatch):
    from wikiquiz_gen.popularity import Kandidat
    from wikiquiz_gen.wikipedia import kandidaten as kand

    monkeypatch.setattr(kand, "artikel_kategorien", lambda http, titel: {
        "Friedrich II. (Preußen)": ["Kategorie:König (Preußen)", "Kategorie:Herrscher (18. Jahrhundert)",
                                    "Kategorie:Komponist (Klassik)"],
        "Mozart": ["Kategorie:Komponist (Klassik)", "Kategorie:Opernkomponist"],
        "Unklar": ["Kategorie:Mann"],
    })
    monkeypatch.setattr(kand, "berufe", lambda http, qids: {})
    ks = [Kandidat("Q1", t, t, 100) for t in ("Friedrich II. (Preußen)", "Mozart", "Unklar")]
    behalten, verworfen = kand.passende_kategorie(None, ks, "kunst")
    assert [k.titel for k in behalten] == ["Mozart", "Unklar"]
    assert verworfen[0][1] == "kategorie passt nicht: geschichte"


def test_themenkategorien_ohne_abgleich(monkeypatch):
    """Schweiz und Star Wars liegen quer zu den Fachkategorien: ein Bundesrat bleibt drin."""
    from wikiquiz_gen.popularity import Kandidat
    from wikiquiz_gen.wikipedia import kandidaten as kand

    monkeypatch.setattr(kand, "artikel_kategorien", lambda http, titel: pytest.fail("kein Abgleich erwartet"))
    ks = [Kandidat("Q1", "Ueli Maurer", "Ueli Maurer", 40)]
    for thema in ("schweiz", "starwars"):
        behalten, verworfen = kand.passende_kategorie(None, ks, thema)
        assert behalten == ks and verworfen == []


def test_zum_thema():
    from wikiquiz_gen.wikipedia.quellen import zum_thema

    assert zum_thema(["Kategorie:Bundesrat (Schweiz)", "Kategorie:Politiker (20. Jahrhundert)"], "schweiz")
    assert zum_thema(["Kategorie:See in der Schweiz"], "schweiz")
    assert zum_thema(["Kategorie:Star-Wars-Film", "Kategorie:Science-Fiction-Film"], "starwars")
    assert not zum_thema(["Kategorie:Science-Fiction-Film"], "starwars")
    assert not zum_thema(["Kategorie:Fluss in Europa"], "schweiz")
    # Themen beeinflussen die Zuordnung zu Fachkategorien nicht
    assert zuordnen(["Kategorie:Bundesrat (Schweiz)", "Kategorie:Politiker (20. Jahrhundert)"]) == "geschichte"
