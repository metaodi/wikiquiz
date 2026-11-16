from datetime import date

from wikiquiz_gen.dedupe import deduplizieren
from wikiquiz_gen.models import Frage, swiss
from wikiquiz_gen.output import lade_kategorie, schreibe_kategorie
from wikiquiz_gen.popularity import ist_listentitel, zeitraum_12_monate
from wikiquiz_gen.sparql import artikel_url, titel_aus_url
from wikiquiz_gen.templates.base import naechste_nach_bekanntheit, schwierigkeit_aus_pageviews, stufen_nach_rang
from wikiquiz_gen.templates.laender import hauptstadt_von, liegt
from wikiquiz_gen.validate import pruefe_formal, verraet_antwort
import random


def frage(**kw) -> Frage:
    basis = dict(
        kategorie="geografie", frage="Wie heisst die Hauptstadt von Kanada?", richtig="Ottawa",
        falsch=["Toronto", "Montreal", "Vancouver"], schwierigkeit=1, quelle_typ="wikidata",
        quelle_url="https://de.wikipedia.org/wiki/Kanada", quelle_titel="Kanada", quelle_id="Q16",
    )
    basis.update(kw)
    return Frage(**basis)


def test_zeitraum_12_monate():
    assert zeitraum_12_monate(date(2026, 11, 15)) == (date(2025, 11, 1), date(2026, 10, 31))
    assert zeitraum_12_monate(date(2026, 1, 3)) == (date(2025, 1, 1), date(2025, 12, 31))


def test_listentitel():
    assert ist_listentitel("Liste der Staaten der Erde")
    assert not ist_listentitel("Listenhof")


def test_url_roundtrip():
    url = artikel_url("Köln (Stadt)")
    assert url == "https://de.wikipedia.org/wiki/K%C3%B6ln_(Stadt)"
    assert titel_aus_url(url) == "Köln (Stadt)"


def test_swiss():
    assert swiss("Großglockner") == "Grossglockner"


def test_laender_grammatik():
    assert hauptstadt_von("Kanada") == "von Kanada"
    assert hauptstadt_von("Schweiz") == "der Schweiz"
    assert hauptstadt_von("Irak") == "des Irak"
    assert hauptstadt_von("Niederlande") == "der Niederlande"
    assert hauptstadt_von("Vereinigtes Königreich") == "des Vereinigten Königreichs"
    assert liegt("Vereinigte Staaten") == "liegen die Vereinigten Staaten"
    assert liegt("Bahamas") == "liegen die Bahamas"
    assert liegt("Ukraine") == "liegt die Ukraine"
    assert liegt("Kanada") == "liegt Kanada"


def test_stufen_nach_rang():
    fragen = [frage(quelle_id=str(i)) for i in range(6)]
    for i, f in enumerate(fragen):
        f.score = i
    stufen_nach_rang(fragen)
    assert [f.schwierigkeit for f in fragen] == [3, 3, 2, 2, 1, 1]


def test_formal_ok():
    assert pruefe_formal(frage()) == []


def test_formal_fehler():
    assert "doppelte antworten" in pruefe_formal(frage(falsch=["Toronto", "toronto", "Montreal"]))
    assert "enthaelt ß" in pruefe_formal(frage(richtig="Großstadt"))
    assert any("distraktoren" in f for f in pruefe_formal(frage(falsch=["A1", "B1"])))
    assert any("zu lang" in f for f in pruefe_formal(frage(frage="x" * 121)))


def test_verraet_antwort():
    assert verraet_antwort("Wie heisst die Hauptstadt von Mexiko?", "Mexiko-Stadt")
    assert not verraet_antwort("Wie heisst die Hauptstadt von Kanada?", "Ottawa")
    # „Stadt“ allein verrät nichts
    assert not verraet_antwort("In welchem Land liegt die Stadt Lyon?", "Republik Stadtland")


def test_id_stabil_und_json():
    f = frage()
    j = f.to_json()
    assert j["id"] == frage().id and j["id"].startswith("wd-")
    assert j["antworten"][j["korrekt_index"]] == "Ottawa"
    assert sorted(j["antworten"]) == sorted(["Ottawa", "Toronto", "Montreal", "Vancouver"])
    assert j["lizenz"] == "CC0"


def test_dedupe():
    a = frage(quelle_typ="wikipedia")
    b = frage(frage="Wie heisst die Hauptstadt von  Kanada ?!", quelle_id="Q99", quelle_typ="wikipedia")
    c = frage(frage="Auf welchem Kontinent liegt Kanada?", richtig="Nordamerika",
              falsch=["Europa", "Asien", "Afrika"])
    d = frage(frage="Welche Sprache spricht man in Kanada?", richtig="Englisch",
              falsch=["Spanisch", "Russisch", "Arabisch"])
    behalten, verworfen = deduplizieren([a, b, c, d])
    assert behalten == [a, c]
    assert len(verworfen) == 2


def test_dedupe_wikidata_templates_nicht_aehnlich():
    a = frage(frage="In welchem Land liegt die Stadt Lyon?", richtig="Frankreich", quelle_id="Q456",
              falsch=["Belgien", "Spanien", "Italien"], template="stadt")
    b = frage(frage="In welchem Land liegt der Berg Lyon?", richtig="Frankreich", quelle_id="Q457",
              falsch=["Belgien", "Spanien", "Italien"], template="berg")
    assert deduplizieren([a, b])[0] == [a, b]


def test_distraktoren_aehnliche_bekanntheit():
    pool = [("A", 100), ("B", 110), ("C", 90), ("D", 100000), ("E", 95)]
    gew = naechste_nach_bekanntheit(100, pool, random.Random(1), n=3, aus=4)
    assert "D" not in gew and len(gew) == 3


def test_schwierigkeit():
    assert schwierigkeit_aus_pageviews(5000) == 1
    assert schwierigkeit_aus_pageviews(1000) == 2
    assert schwierigkeit_aus_pageviews(300) == 3


def test_schreibe_kategorie_modi(tmp_path):
    a = frage().to_json()
    c = frage(frage="Auf welchem Kontinent liegt Kanada?", richtig="Nordamerika",
              falsch=["Europa", "Asien", "Afrika"]).to_json()
    w = frage(quelle_typ="wikipedia", frage="Welche Sprache spricht man in Kanada?", richtig="Englisch",
              falsch=["Spanisch", "Russisch", "Arabisch"]).to_json()
    schreibe_kategorie("geografie", [a, w], {"wikidata", "wikipedia"}, verzeichnis=tmp_path)
    schreibe_kategorie("geografie", [c], {"wikidata"}, modus="ergaenzen", verzeichnis=tmp_path)
    assert {f["id"] for f in lade_kategorie("geografie", tmp_path)} == {a["id"], c["id"], w["id"]}
    # ersetzen betrifft nur die angegebene Quelle
    schreibe_kategorie("geografie", [c], {"wikidata"}, modus="ersetzen", verzeichnis=tmp_path)
    assert {f["id"] for f in lade_kategorie("geografie", tmp_path)} == {c["id"], w["id"]}


def test_anfuehrungszeichen():
    from wikiquiz_gen.models import anfuehrungszeichen, text_bereinigen

    assert anfuehrungszeichen("Wer schrieb ‚Rigoletto‘?") == "Wer schrieb «Rigoletto»?"
    assert anfuehrungszeichen("„Faust“ und \"Hamlet\" und “Carmen”") == "«Faust» und «Hamlet» und «Carmen»"
    assert anfuehrungszeichen("«Der Report der Magd» (The Handmaid’s Tale)") == "«Der Report der Magd» (The Handmaid’s Tale)"
    assert text_bereinigen("  ‚Großes‘ Haus ") == "«Grosses» Haus"
    # Die ID hängt nicht an Satzzeichen: Bereinigen ändert sie nicht
    assert frage(frage="Wer schrieb ‚Faust‘?").id == frage(frage="Wer schrieb «Faust»?").id


def test_verschieben(tmp_path):
    from wikiquiz_gen.output import lade_kategorie, schreibe_kategorie, verschieben
    import pytest

    a = frage(kategorie="kunst", quelle_typ="wikipedia", frage="Wer formulierte die Planetengesetze?",
              richtig="Kepler", falsch=["Brahe", "Galilei", "Kopernikus"]).to_json()
    b = frage(kategorie="kunst", quelle_typ="wikipedia").to_json()
    schreibe_kategorie("kunst", [a, b], {"wikipedia"}, verzeichnis=tmp_path)
    verschoben = verschieben([a["id"]], "naturwissenschaften", verzeichnis=tmp_path)
    assert [f["id"] for f in verschoben] == [a["id"]]
    assert [f["id"] for f in lade_kategorie("kunst", tmp_path)] == [b["id"]]
    ziel = lade_kategorie("naturwissenschaften", tmp_path)
    assert ziel[0]["id"] == a["id"] and ziel[0]["kategorie"] == "naturwissenschaften"
    with pytest.raises(ValueError):
        verschieben(["wp-gibtsnicht"], "geschichte", verzeichnis=tmp_path)
