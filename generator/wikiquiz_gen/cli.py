"""Kommandozeile des Fragen-Generators.

Beispiele:
  python -m wikiquiz_gen generate --kategorie kunst --quelle wikipedia --ziel 150 --max-artikel 40
  python -m wikiquiz_gen generate --kategorie kunst --quelle wikipedia --nur-kandidaten
  python -m wikiquiz_gen generate --kategorie geografie --quelle wikidata --modus ersetzen
  python -m wikiquiz_gen review --kategorie kunst --n 30
  python -m wikiquiz_gen verschieben --nach naturwissenschaften --id wp-…
  python -m wikiquiz_gen entfernen --id wp-… --id wp-…
  python -m wikiquiz_gen stats
"""
from __future__ import annotations

import argparse
import dataclasses
import logging
import os
import sys
from collections import Counter

from . import output, pipeline
from .config import KATEGORIEN, OUT_DIR, SCHWELLEN
from .http import Http
from .popularity import Bekanntheit
from .review import stichprobe_markdown
from .templates.base import Kontext

log = logging.getLogger("wikiquiz_gen")


def _schwellen(kategorie: str, args: argparse.Namespace):
    s = SCHWELLEN[kategorie]
    ueber = {
        k: v
        for k, v in {
            "min_sitelinks": args.min_sitelinks,
            "min_pageviews": args.min_pageviews,
            "min_pageviews_antwort": args.min_pageviews_antwort,
            "min_zeichen": args.min_zeichen,
        }.items()
        if v is not None
    }
    return dataclasses.replace(s, **ueber)


def cmd_generate(args: argparse.Namespace) -> int:
    http = Http(nur_cache=args.nur_cache)
    bekanntheit = Bekanntheit(http, exakt=args.pageviews_exakt)
    protokoll = output.Protokoll(aktiv=not args.dry_run)
    kategorien = args.kategorie or list(KATEGORIEN)
    alle_neuen: list[dict] = []
    zusammenfassung: list[str] = []
    for kat in kategorien:
        schwellen = _schwellen(kat, args)
        log.info("== %s (%s) ==", KATEGORIEN[kat], schwellen)
        ktx = Kontext(kat, http, bekanntheit, schwellen, protokoll,
                      max_kandidaten=args.max_kandidaten, seed=args.seed)
        bestand = output.lade_kategorie(kat)
        andere = [f for k in KATEGORIEN if k != kat for f in output.lade_kategorie(k)]
        neue: list[dict] = []
        quellen: set[str] = set()
        zeilen = [f"### {KATEGORIEN[kat]}", "", f"Bestand vorher: {len(bestand)} Fragen"]

        if args.quelle in ("wikidata", "alle") and kat in pipeline.WIKIDATA_TEMPLATES:
            fragen = pipeline.wikidata(ktx, args.ziel)
            neue += [f.to_json() for f in fragen]
            quellen.add("wikidata")
            vorlagen = Counter(f.template for f in fragen)
            zeilen.append(f"Wikidata: {len(fragen)} Fragen ({', '.join(f'{k} {v}' for k, v in vorlagen.items())})")

        if args.quelle in ("wikipedia", "alle"):
            verarbeitet = output.lade_verarbeitet(kat)
            fragen, neu_verarbeitet, verbrauch = pipeline.wikipedia(
                ktx, args.ziel, args.max_artikel, bestand, verarbeitet,
                threads=args.threads, nur_kandidaten=args.nur_kandidaten, andere=andere,
            )
            neue += [f.to_json() for f in fragen]
            quellen.add("wikipedia")
            if verbrauch:
                zeilen.append(
                    f"Wikipedia + LLM: {len(fragen)} neue Fragen aus {len(neu_verarbeitet)} Artikeln · "
                    f"{verbrauch.aufrufe} LLM-Aufrufe · {verbrauch.eingabe:,} / {verbrauch.ausgabe:,} Tokens "
                    f"(ein/aus) · ca. {verbrauch.kosten_usd:.2f} USD"
                )
            if not args.dry_run and neu_verarbeitet:
                output.schreibe_verarbeitet(kat, {**verarbeitet, **neu_verarbeitet})

        neue, doppelt = pipeline.ohne_fremde_ids(neue, andere)
        for f in doppelt:
            protokoll.verwerfen(kat, "dedupe", f"id schon in anderer kategorie: {f['id']}",
                                {"frage": f["frage"], "titel": f.get("quelle_titel", "")})

        if not args.dry_run and not args.nur_kandidaten and neue:
            # „ersetzen“ gilt nur für Wikidata-Fragen (deterministisch neu erzeugbar). Wikipedia-Fragen
            # werden immer nur ergänzt: Die Pipeline erzeugt nur den fehlenden Bedarf, ein Ersetzen
            # würde bereits bezahlte Fragen löschen.
            ersetzen = output.ersetzbare_quellen(args.modus, quellen)
            fragen_kat = output.schreibe_kategorie(kat, neue, ersetzen,
                                                   modus="ersetzen" if ersetzen else "ergaenzen")
            zeilen.append(f"Bestand nachher: {len(fragen_kat)} Fragen")
        alle_neuen += neue
        zusammenfassung += zeilen + [""]

    gruende = Counter(e["stufe"] + ": " + e["grund"].split(":")[0].split(" ")[0] for e in protokoll.eintraege)
    zusammenfassung.append("Verworfen: " + (", ".join(f"{k} ×{v}" for k, v in gruende.most_common(12)) or "–"))
    zusammenfassung.append(f"HTTP: {http.stats['netz']} Netz, {http.stats['cache']} Cache")
    text = "\n".join(zusammenfassung)
    print(text)
    protokoll.speichern()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "zusammenfassung.md").write_text(text + "\n", encoding="utf-8")
    for kat in kategorien:
        neu_kat = [f for f in alle_neuen if f["kategorie"] == kat]
        if neu_kat:
            md = stichprobe_markdown(neu_kat, kat, n=args.stichprobe, seed=args.seed, titel="Neue Fragen")
            (OUT_DIR / "review").mkdir(parents=True, exist_ok=True)
            (OUT_DIR / "review" / f"{kat}-neu.md").write_text(md + "\n", encoding="utf-8")
            if args.dry_run:
                print()
                print(md)
    if args.dry_run:
        print("\nTrockenlauf: keine Fragen geschrieben.")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    fragen = output.lade_alle()
    kategorien = args.kategorie or sorted({f["kategorie"] for f in fragen})
    ziel = OUT_DIR / "review"
    ziel.mkdir(parents=True, exist_ok=True)
    for kat in kategorien:
        md = stichprobe_markdown(fragen, kat, n=args.n, seed=args.seed)
        (ziel / f"{kat}.md").write_text(md + "\n", encoding="utf-8")
        print(md)
        print()
    print(f"Gespeichert in {ziel}/", file=sys.stderr)
    return 0


def cmd_verschieben(args: argparse.Namespace) -> int:
    try:
        verschoben = output.verschieben(args.id, args.nach)
    except ValueError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    for f in verschoben:
        print(f"{f['id']} → {args.nach}: {f['frage']}")
    return 0


def cmd_entfernen(args: argparse.Namespace) -> int:
    try:
        entfernt = output.entfernen(args.id)
    except ValueError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    for f in entfernt:
        print(f"{f['id']} entfernt ({f['kategorie']}): {f['frage']}")
    return 0


def cmd_bereinigen(args: argparse.Namespace) -> int:
    """Anführungszeichen und Schweizer Rechtschreibung in bestehenden Fragen vereinheitlichen.
    Die IDs ändern sich dadurch nicht (Satzzeichen fliessen nicht in die ID ein)."""
    from .models import text_bereinigen

    geaendert = 0
    for kat in args.kategorie or list(KATEGORIEN):
        fragen = output.lade_kategorie(kat)
        if not fragen:
            continue
        neu, geaendert_kat = [], 0
        for f in fragen:
            g = {**f, "frage": text_bereinigen(f["frage"]),
                 "antworten": [text_bereinigen(a) for a in f["antworten"]]}
            if g != f:
                geaendert_kat += 1
                print(f"{f['id']}: {f['frage']}  →  {g['frage']}")
            neu.append(g)
        geaendert += geaendert_kat
        # Nur Dateien mit Änderungen schreiben (sonst ändert sich unnötig der Zeitstempel)
        if geaendert_kat and not args.dry_run:
            output.speichere_kategorie(kat, neu)
    print(f"{geaendert} Fragen angepasst" + (" (Trockenlauf)" if args.dry_run else ""))
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    fragen = output.lade_alle()
    c = Counter((f["kategorie"], f["quelle_typ"]) for f in fragen)
    for kat in KATEGORIEN:
        wd, wp = c[(kat, "wikidata")], c[(kat, "wikipedia")]
        print(f"{KATEGORIEN[kat]:32} {wd + wp:5}  (wikidata {wd}, wikipedia {wp})")
    print(f"{'Total':32} {len(fragen):5}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wikiquiz-gen", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="Fragen erzeugen")
    g.add_argument("--kategorie", action="append", choices=list(KATEGORIEN))
    g.add_argument("--quelle", choices=["wikidata", "wikipedia", "alle"], default="alle")
    g.add_argument("--ziel", type=int, default=150,
                   help="Wikidata: max. Fragen; Wikipedia: Zielbestand (es wird nur die Differenz erzeugt)")
    g.add_argument("--max-artikel", type=int, default=40, help="max. Wikipedia-Artikel pro Lauf (Kostenbremse)")
    g.add_argument("--threads", type=int, default=4, help="parallele LLM-Aufrufe")
    g.add_argument("--nur-kandidaten", action="store_true", help="nur Artikelkandidaten auflisten, kein LLM")
    g.add_argument("--min-sitelinks", type=int)
    g.add_argument("--min-pageviews", type=float)
    g.add_argument("--min-pageviews-antwort", type=float)
    g.add_argument("--min-zeichen", type=int)
    g.add_argument("--pageviews-exakt", action="store_true",
                   help="12-Monats-Werte für alle Kandidaten (sonst nur im Graubereich)")
    g.add_argument("--max-kandidaten", type=int, default=300, help="pro Template aus SPARQL")
    g.add_argument("--modus", choices=["ersetzen", "ergaenzen"], default="ergaenzen",
                   help="ersetzen: Wikidata-Fragen der Kategorie neu erzeugen (Wikipedia-Fragen bleiben immer)")
    g.add_argument("--seed", type=int, default=42)
    g.add_argument("--dry-run", action="store_true",
                   help="Trockenlauf: Fragen erzeugen (inkl. LLM), aber nichts in data/ schreiben")
    g.add_argument("--stichprobe", type=int, default=30)
    g.add_argument("--nur-cache", action="store_true", help="keine Netzwerkzugriffe")
    g.set_defaults(func=cmd_generate)

    r = sub.add_parser("review", help="Markdown-Stichprobe aus data/fragen/")
    r.add_argument("--kategorie", action="append", choices=list(KATEGORIEN))
    r.add_argument("--n", type=int, default=30)
    r.add_argument("--seed", type=int, default=1)
    r.set_defaults(func=cmd_review)

    v = sub.add_parser("verschieben", help="Fragen per ID in eine andere Kategorie verschieben")
    v.add_argument("--id", action="append", required=True, help="Frage-ID (mehrfach möglich)")
    v.add_argument("--nach", required=True, choices=list(KATEGORIEN))
    v.set_defaults(func=cmd_verschieben)

    e = sub.add_parser("entfernen", help="Fragen per ID löschen (Artikel bleibt als verarbeitet vermerkt)")
    e.add_argument("--id", action="append", required=True, help="Frage-ID (mehrfach möglich)")
    e.set_defaults(func=cmd_entfernen)

    b = sub.add_parser("bereinigen", help="Anführungszeichen/Rechtschreibung vereinheitlichen")
    b.add_argument("--kategorie", action="append", choices=list(KATEGORIEN))
    b.add_argument("--dry-run", action="store_true")
    b.set_defaults(func=cmd_bereinigen)

    s = sub.add_parser("stats", help="Anzahl Fragen pro Kategorie")
    s.set_defaults(func=cmd_stats)

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    try:
        return args.func(args)
    except Exception as e:
        from .llm.client import AnmeldeFehler, LLMFehler

        if isinstance(e, LLMFehler):
            print(f"::error::{e}", file=sys.stderr)
            return 3
        if not isinstance(e, AnmeldeFehler):
            raise
        hinweis = (
            "Föderation: Grund in der Claude Console unter Workload identity → Authentication history"
            if os.environ.get("ANTHROPIC_FEDERATION_RULE_ID") else "API-Key prüfen (ANTHROPIC_API_KEY)"
        )
        print(f"::error::Anmeldung bei Anthropic fehlgeschlagen: {e} – {hinweis}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
