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


def test_ersetzen_loescht_nie_wikipedia_fragen(tmp_path):
    from wikiquiz_gen.output import ersetzbare_quellen, lade_kategorie, schreibe_kategorie

    assert ersetzbare_quellen("ersetzen", {"wikidata", "wikipedia"}) == {"wikidata"}
    assert ersetzbare_quellen("ersetzen", {"wikipedia"}) == set()
    assert ersetzbare_quellen("ergaenzen", {"wikidata"}) == set()

    alt_wd = frage().to_json()
    alt_wp = frage(quelle_typ="wikipedia", frage="Welche Sprache spricht man in Kanada?", richtig="Englisch",
                   falsch=["Spanisch", "Russisch", "Arabisch"]).to_json()
    schreibe_kategorie("geografie", [alt_wd, alt_wp], set(), verzeichnis=tmp_path)
    neu_wd = frage(frage="Auf welchem Kontinent liegt Kanada?", richtig="Nordamerika",
                   falsch=["Europa", "Asien", "Afrika"]).to_json()
    # Lauf mit Quelle „alle“ und Modus „ersetzen“: alte Wikidata-Frage weg, Wikipedia-Frage bleibt
    ersetzen = ersetzbare_quellen("ersetzen", {"wikidata", "wikipedia"})
    schreibe_kategorie("geografie", [neu_wd], ersetzen, modus="ersetzen", verzeichnis=tmp_path)
    assert {f["id"] for f in lade_kategorie("geografie", tmp_path)} == {neu_wd["id"], alt_wp["id"]}


def test_dedupe_gleiche_tatsache_und_gegenseitig_verraten():
    wp = dict(quelle_typ="wikipedia")
    polen = frage(**wp, quelle_id="Q1", frage="Mit welchem Ereignis begann der Zweite Weltkrieg in Europa am 1. September 1939?",
                  richtig="Deutscher Überfall auf Polen", falsch=["Münchner Abkommen", "Anschluss Österreichs", "Reichstagsbrand"])
    hitler = frage(**wp, quelle_id="Q2", frage="Mit welchem Ereignis löste Hitler im September 1939 den Zweiten Weltkrieg in Europa aus?",
                   richtig="Überfall auf Polen", falsch=["Münchner Abkommen", "Anschluss Österreichs", "Reichstagsbrand"])
    obama = frage(**wp, quelle_id="Q3", frage="Wer war während beider Amtszeiten von Barack Obama Vizepräsident der USA?",
                  richtig="Joe Biden", falsch=["Al Gore", "Dick Cheney", "Mike Pence"])
    biden = frage(**wp, quelle_id="Q4", frage="Unter welchem US-Präsidenten war Joe Biden von 2009 bis 2017 Vizepräsident?",
                  richtig="Barack Obama", falsch=["Bill Clinton", "George W. Bush", "Donald Trump"])
    # Gleiche Antwort, aber verschiedene Werke: keine Dublette
    zauber = frage(**wp, quelle_id="Q5", frage="Welcher Komponist schrieb die Oper «Die Zauberflöte»?",
                   richtig="Wolfgang Amadeus Mozart", falsch=["Haydn", "Salieri", "Gluck"])
    giovanni = frage(**wp, quelle_id="Q6", frage="Welcher Komponist schrieb die Oper «Don Giovanni»?",
                     richtig="Wolfgang Amadeus Mozart", falsch=["Haydn", "Salieri", "Gluck"])
    # Die Gewichtung braucht einen Bestand, in dem Fragewörter wie „Komponist“ häufig sind
    bestand = [frage(**wp, quelle_id=f"F{i}", frage=f"Welcher Komponist schrieb die Oper «{t}»?", richtig=r,
                     falsch=["Haydn", "Salieri", "Gluck"])
               for i, (t, r) in enumerate([("Aida", "Verdi"), ("Carmen", "Bizet"), ("Tosca", "Puccini"),
                                           ("Fidelio", "Beethoven"), ("Lohengrin", "Wagner"), ("Norma", "Bellini")])]
    behalten, verworfen = deduplizieren([*bestand, polen, hitler, obama, biden, zauber, giovanni])
    assert behalten == [*bestand, polen, obama, zauber, giovanni]
    assert [g.split()[0] for _, g in verworfen] == ["gleiche", "verraet"]


def test_entfernen(tmp_path):
    from wikiquiz_gen.output import entfernen, lade_kategorie, schreibe_kategorie
    import pytest

    a = frage(kategorie="geschichte", quelle_typ="wikipedia").to_json()
    b = frage(kategorie="geschichte", quelle_typ="wikipedia", frage="Auf welchem Kontinent liegt Kanada?",
              richtig="Nordamerika", falsch=["Europa", "Asien", "Afrika"]).to_json()
    schreibe_kategorie("geschichte", [a, b], {"wikipedia"}, verzeichnis=tmp_path)
    assert [f["id"] for f in entfernen([a["id"]], verzeichnis=tmp_path)] == [a["id"]]
    assert [f["id"] for f in lade_kategorie("geschichte", tmp_path)] == [b["id"]]
    with pytest.raises(ValueError):
        entfernen([a["id"]], verzeichnis=tmp_path)


def test_epoche_aus_kategorien():
    from wikiquiz_gen.wikipedia.themen import jahr_schaetzen, thema

    assert jahr_schaetzen(["Kategorie:Geboren 1638", "Kategorie:Gestorben 1715"]) == 1638 + 0.6 * 77
    assert jahr_schaetzen(["Kategorie:Geboren 69 v. Chr.", "Kategorie:Gestorben 30 v. Chr."]) < 0
    assert jahr_schaetzen(["Kategorie:Herrscher (17. Jahrhundert)"]) == 1650
    assert jahr_schaetzen(["Kategorie:Konflikt 1962", "Kategorie:Kalter Krieg"]) == 1962
    assert jahr_schaetzen(["Kategorie:Boeing 747"]) is None
    assert thema("geschichte", ["Kategorie:Schlacht (1. Jahrhundert)", "Kategorie:9"], None) == "Antike"
    # NS-Zeit hat Vorrang vor der Lebensspanne (Mengele 1911–1979)
    assert thema("geschichte", ["Kategorie:Geboren 1911", "Kategorie:Gestorben 1979", "Kategorie:SS-Mitglied"], None) == "1914–1945"
    assert thema("geschichte", [], None, datum_jahr=1989) == "seit 1945"
    # Ohne Jahr: ein gemeinsamer Topf statt der Startkategorie
    assert thema("geschichte", ["Kategorie:Flughafen in Berlin"], "Exzellent/Lesenswert") == "ohne Epoche"
    assert thema("kunst", ["Kategorie:Geboren 1756"], "Kategorie:Oper") == "Kategorie:Oper"


def test_themen_ausgleichen():
    from collections import Counter

    from wikiquiz_gen.wikipedia.themen import ausgleichen

    # nach Seitenaufrufen sortiert: zuerst drei Artikel zur NS-Zeit
    kandidaten = [("Hitler", "ns"), ("Stalingrad", "ns"), ("Gestapo", "ns"), ("Caesar", "antike"), ("Luther", "neuzeit")]
    geordnet = ausgleichen(kandidaten, lambda k: k[1], Counter({"ns": 10, "antike": 2}))
    assert [k[0] for k in geordnet] == ["Luther", "Caesar", "Hitler", "Stalingrad", "Gestapo"]


def test_flugzeuge_sind_technik():
    from wikiquiz_gen.wikipedia.quellen import zuordnen

    assert zuordnen(["Kategorie:Erstflug 1970", "Kategorie:Militärluftfahrzeug (Vereinigte Staaten)",
                     "Kategorie:Militärluftfahrzeug (Iran)", "Kategorie:Trägergestütztes Flugzeug"]) == "naturwissenschaften"


def _schweiz_testdaten():
    from wikiquiz_gen.config import SCHWELLEN
    from wikiquiz_gen.output import Protokoll
    from wikiquiz_gen.popularity import Kandidat
    from wikiquiz_gen.templates.base import Kontext
    from wikiquiz_gen.templates.schweiz import Kanton

    ktx = Kontext("schweiz", None, None, SCHWELLEN["schweiz"], Protokoll(aktiv=False))

    def kanton(q, name, sprachen, hauptort=None):
        return Kanton(k=Kandidat(qid=q, label=f"Kanton {name}", titel=f"Kanton {name}", sitelinks=100),
                      hauptorte={hauptort} if hauptort else set(), sprachen=set(sprachen))

    kantone = {
        "K1": kanton("K1", "Tessin", ["Italienisch"], "G1"),
        "K2": kanton("K2", "Bern", ["Deutsch", "Französisch"], "G5"),
        "K3": kanton("K3", "Graubünden", ["Deutsch", "Italienisch", "Rätoromanisch"]),
        "K4": kanton("K4", "Freiburg", ["Deutsch", "Französisch"]),
        "K5": kanton("K5", "Wallis", ["Deutsch", "Französisch"]),
        "K6": kanton("K6", "Uri", ["Deutsch"]),
        "K7": kanton("K7", "Zug", ["Deutsch"], "G6"),
    }
    return ktx, kantone


def test_schweiz_hauptort_mit_gemeinden_des_kantons():
    from wikiquiz_gen.templates.schweiz import hauptort

    ktx, kantone = _schweiz_testdaten()
    gemeinden = [
        {"item": f"http://www.wikidata.org/entity/{q}", "label": n, "kantone": k, "einwohner": str(e)}
        for q, n, k, e in [("G1", "Bellinzona", "K1", 45000), ("G2", "Lugano", "K1", 63000),
                           ("G3", "Locarno", "K1", 16000), ("G4", "Mendrisio", "K1", 15000),
                           ("G5", "Bern", "K2", 134000), ("G6", "Zug", "K7", 31000), ("G7", "Baar", "K7", 25000),
                           ("G8", "Cham", "K7", 17000), ("G9", "Risch", "K7", 11000)]
    ]
    fragen = hauptort(ktx, kantone, gemeinden)
    # Bern: zu wenige Gemeinden im Test; Zug: Hauptort steckt im Namen; die übrigen ohne Hauptort
    assert len(fragen) == 1
    f = fragen[0]
    assert f.frage == "Wie heisst der Hauptort des Kantons Tessin?" and f.richtig == "Bellinzona"
    assert sorted(f.falsch) == ["Locarno", "Lugano", "Mendrisio"]


def test_schweiz_sprache():
    from wikiquiz_gen.templates.schweiz import sprache

    ktx, kantone = _schweiz_testdaten()
    fragen = {f.frage: f for f in sprache(ktx, kantone)}
    tessin = fragen["Welche Amtssprache hat der Kanton Tessin?"]
    assert tessin.richtig == "Italienisch" and sorted(tessin.falsch) == ["Deutsch", "Französisch", "Rätoromanisch"]
    drei = fragen["Welcher Kanton hat drei Amtssprachen?"]
    assert drei.richtig == "Graubünden" and sorted(drei.falsch) == ["Bern", "Freiburg", "Wallis"]
    assert len(fragen) == 2  # Uri (deutschsprachig) wird nicht gefragt


def test_landessprache():
    from wikiquiz_gen.templates.schweiz import landessprache

    assert landessprache("Schweizer Hochdeutsch") == "Deutsch"
    assert landessprache("Schweizer Französisch") == "Französisch"
    assert landessprache("Bündnerromanisch") == "Rätoromanisch"
    assert landessprache("Italienisch") == "Italienisch"
    assert landessprache("Latein") is None


def test_dedupe_gleiche_antwort_hoechstens_zweimal():
    from wikiquiz_gen.dedupe import antwort_schluessel

    def wp(text, richtig, qid, falsch=("Ridley Scott", "James Cameron", "Steven Spielberg")):
        return frage(frage=text, richtig=richtig, falsch=list(falsch), quelle_id=qid, quelle_typ="wikipedia")

    lucas = [
        wp("Welcher Filmemacher erfand die Weltraum-Saga Star Wars?", "George Lucas", "Q1"),
        wp("Wer führte Regie bei Episode II?", "George Lucas", "Q2"),
        wp("Wer schrieb das Drehbuch zum Film von 1977?", "George Lucas", "Q3"),
    ]
    todesstern = [
        wp("Welche Raumstation zerstört Alderaan?", "Der Todesstern", "Q4", ("Sternzerstörer", "Executor", "Kampfstern")),
        wp("Welche Station befehligt Tarkin?", "Den Todesstern", "Q5", ("Sternzerstörer", "Executor", "Kampfstern")),
        wp("Wie heisst die Kampfstation des Imperiums?", "Todesstern", "Q6", ("Sternzerstörer", "Executor", "Kampfstern")),
    ]
    jahre = [wp(t, "1977", f"Q{10 + i}", ("1971", "1985", "1983")) for i, t in enumerate([
        "Wann kam Krieg der Sterne in die Kinos?", "In welchem Jahr starb Elvis Presley?",
        "Wann startete die Raumsonde Voyager 1?"])]
    behalten, verworfen = deduplizieren([*lucas, *todesstern, *jahre])
    assert behalten == [*lucas[:2], *todesstern[:2], *jahre]
    assert [g for _, g in verworfen] == ["gleiche antwort: schon 2 fragen mit «George Lucas»",
                                          "gleiche antwort: schon 2 fragen mit «Todesstern»"]
    assert antwort_schluessel("Der Todesstern") == antwort_schluessel("todesstern") == "todesstern"
    assert antwort_schluessel("1977") is None


def test_dedupe_gleiche_antwort_nicht_fuer_wikidata():
    fragen = [frage(frage=f"In welchem Land liegt die Stadt {s}?", richtig="Frankreich", quelle_id=f"Q{i}",
                    falsch=["Belgien", "Spanien", "Italien"], template="stadt")
              for i, s in enumerate(["Lyon", "Lille", "Nizza"])]
    assert deduplizieren(fragen)[0] == fragen


def test_zeitgenossen_und_geburtsjahr():
    from wikiquiz_gen.templates.base import zeitgenossen
    from wikiquiz_gen.templates.kunst import geburtsjahr

    assert geburtsjahr("1564-04-23T00:00:00Z") == 1564
    assert geburtsjahr("-0496-01-01T00:00:00Z") == -496
    pool = [("Goethe", 1749), ("Schiller", 1759), ("Kleist", 1777), ("Novalis", 1772), ("Brecht", 1898),
            ("Lessing", 1729), ("Homer", -800)]
    gew = zeitgenossen(pool, 1749, {"Goethe"}, random.Random(1), n=3, aus=4)
    assert len(gew) == 3 and "Goethe" not in gew and not {"Brecht", "Homer"} & set(gew)
    assert zeitgenossen(pool[:3], 1749, {"Goethe"}, random.Random(1)) == []  # zu wenige


def test_sport_wm_name_und_olympia_orte():
    from wikiquiz_gen.templates.sport import SOMMER_ORTE, WINTER_ORTE, _jahr, _wm_name

    assert _wm_name("Fußball-Weltmeisterschaft 2014") == "Fussball-Weltmeisterschaft 2014"
    assert _wm_name("Fußball-Weltmeisterschaft 2018/Qualifikation (UEFA)/Gruppe C") is None
    assert _wm_name("Fußball-Weltmeisterschaft der Frauen 2019") is None
    assert _jahr("Olympische Sommerspiele 1972") == 1972
    assert SOMMER_ORTE[1972] == "München" and WINTER_ORTE[1928] == "St. Moritz"
    # Ausgefallene Spiele (Weltkriege) und Spiele mit mehreren Gastgebern fehlen
    assert not {1916, 1940, 1944} & SOMMER_ORTE.keys() and 2026 not in WINTER_ORTE


def test_urheber_pool_ohne_unbekannte_geburtsjahre():
    from wikiquiz_gen.templates.kunst import geburtsjahr, urheber_pool

    assert geburtsjahr("http://www.wikidata.org/.well-known/genid/abc") is None
    assert geburtsjahr(None) is None
    rows = [
        {"person": "P1", "pl": "James Cameron", "geboren": "1954-08-16T00:00:00Z"},
        {"person": "P1", "pl": "James Cameron", "geboren": "1954-08-16T00:00:00Z"},  # zwei Filme
        {"person": "P2", "pl": "Unbekannt", "geboren": "http://www.wikidata.org/.well-known/genid/x"},
    ]
    assert urheber_pool(rows) == [("James Cameron", 1954)]


def test_artikel_aus_anderen_kategorien():
    from wikiquiz_gen.pipeline import ohne_fremde_ids, themen_anderer_kategorien
    from wikiquiz_gen.popularity import Kandidat

    andere = [{"id": "wp-44eabfbbb6", "kategorie": "essen", "quelle_id": "Q29506"},
              {"id": "wp-f942ddca42", "kategorie": "kunst", "quelle_id": "Q25973"}]
    kaki, eiche = Kandidat("Q29506", "Kaki", "Kaki", 80), Kandidat("Q12004", "Eichen", "Eichen", 90)
    behalten, verworfen = themen_anderer_kategorien([kaki, eiche], andere)
    assert behalten == [eiche] and verworfen == [(kaki, "schon in kategorie essen")]

    neu = [{"id": "wp-f942ddca42", "frage": "Hesse?"}, {"id": "wp-neu", "frage": "Eiche?"}]
    ok, doppelt = ohne_fremde_ids(neu, andere)
    assert [f["id"] for f in ok] == ["wp-neu"] and [f["id"] for f in doppelt] == ["wp-f942ddca42"]


def test_dedupe_gleiches_werk_wikidata_gegen_bestand():
    def wp(text, richtig, qid):
        return frage(frage=text, richtig=richtig, falsch=["A B", "C D", "E F"], quelle_id=qid, quelle_typ="wikipedia")

    def wd(text, richtig, qid):
        return frage(frage=text, richtig=richtig, falsch=["A B", "C D", "E F"], quelle_id=qid, template="x")

    # Lauf 30 (kunst): Wortüberlappung nur 0.14–0.36, trotzdem dieselbe Tatsache
    bestand = [
        wp("Welcher Maler schuf das berühmte Gemälde «Die Nachtwache»?", "Rembrandt", "Q1"),
        wp("Welcher italienische Komponist schrieb die Opern «Tosca» und «Madama Butterfly»?", "Giacomo Puccini", "Q2"),
    ]
    neu = [
        wd("Wer malte das Gemälde «Die Nachtwache»?", "Rembrandt van Rijn", "Q3"),
        wd("Wer komponierte die Oper «Tosca»?", "Giacomo Puccini", "Q4"),
        wd("Wer komponierte die Oper «Aida»?", "Giuseppe Verdi", "Q5"),
        # gleicher Titel, andere Antwort: bleibt
        wd("Wer schrieb «Tosca»?", "Victorien Sardou", "Q6"),
    ]
    behalten, verworfen = deduplizieren([*bestand, *neu])
    assert behalten == [*bestand, *neu[2:]]
    assert [g for _, g in verworfen] == [f"gleiches werk wie {bestand[0].id}", f"gleiches werk wie {bestand[1].id}"]
