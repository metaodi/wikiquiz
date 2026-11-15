from wikiquiz_gen.config import REPO_DIR
from wikiquiz_gen.llm.prompts import GENERIERUNG_SYSTEM, GENERIERUNG_USER, PRUEFUNG, fuellen


def test_prompts_entsprechen_spec():
    spec = (REPO_DIR / "SPEC.md").read_text(encoding="utf-8")
    assert GENERIERUNG_SYSTEM in spec
    assert GENERIERUNG_USER in spec
    assert PRUEFUNG in spec


def test_platzhalter():
    for p in ("{kategorie}", "{n}", "{bestehende_fragen}", "{titel}", "{text}"):
        assert p in GENERIERUNG_USER
    for p in ("{frage}", "{a}", "{b}", "{c}", "{d}", "{text}"):
        assert p in PRUEFUNG
    gefuellt = fuellen(PRUEFUNG, frage="F?", a="1", b="2", c="3", d="4", text="T")
    assert "Antworten (gemischt): 1, 2, 3, 4" in gefuellt
    assert '"deine_antwort": "string"' in gefuellt  # JSON-Klammern bleiben erhalten
