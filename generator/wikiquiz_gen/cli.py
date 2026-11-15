"""Kommandozeile des Fragen-Generators.

Beispiele:
  python -m wikiquiz_gen generate --kategorie geografie --ziel 150
  python -m wikiquiz_gen generate --kategorie geografie --dry-run --min-pageviews 500
  python -m wikiquiz_gen review --kategorie geografie --n 30
  python -m wikiquiz_gen stats
"""
from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
from collections import Counter

from . import output, pipeline
from .config import KATEGORIEN, OUT_DIR, QUESTIONS_PATH, SCHWELLEN
from .http import Http
from .popularity import Bekanntheit
from .review import stichprobe_markdown
from .templates.base import Kontext


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
    kategorien = args.kategorie or list(pipeline.WIKIDATA_TEMPLATES)
    neue: list[dict] = []
    bereiche: set[tuple[str, str]] = set()
    for kat in kategorien:
        schwellen = _schwellen(kat, args)
        logging.info("== %s (%s) ==", KATEGORIEN[kat], schwellen)
        ktx = Kontext(kat, http, bekanntheit, schwellen, protokoll,
                      max_kandidaten=args.max_kandidaten, seed=args.seed)
        if args.quelle in ("wikidata", "alle"):
            fragen = pipeline.wikidata(ktx, args.ziel)
            neue += [f.to_json() for f in fragen]
            bereiche.add((kat, "wikidata"))
            vorlagen = Counter(f.template for f in fragen)
            print(f"{KATEGORIEN[kat]}: {len(fragen)} Wikidata-Fragen "
                  f"({', '.join(f'{k} {v}' for k, v in vorlagen.items())})")
        if args.quelle in ("wikipedia", "alle"):
            print(f"{KATEGORIEN[kat]}: LLM-Pipeline folgt in Schritt 3")
    gruende = Counter(e["stufe"] + ": " + e["grund"].split(" ")[0] for e in protokoll.eintraege)
    print("Verworfen:", ", ".join(f"{k} ×{v}" for k, v in gruende.most_common(10)) or "–")
    print(f"HTTP: {http.stats['netz']} Netz, {http.stats['cache']} Cache")

    if args.dry_run:
        print("Trockenlauf: nichts geschrieben.")
        for kat in kategorien:
            print()
            print(stichprobe_markdown(neue, kat, n=args.stichprobe, seed=args.seed))
        return 0
    protokoll.speichern()
    pool = output.schreibe_pool(neue, bereiche, modus=args.modus)
    print(f"{QUESTIONS_PATH}: {len(pool['fragen'])} Fragen total; verworfen → {protokoll.pfad}")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    pool = output.lade_pool()
    kategorien = args.kategorie or sorted({f["kategorie"] for f in pool["fragen"]})
    ziel = OUT_DIR / "review"
    ziel.mkdir(parents=True, exist_ok=True)
    for kat in kategorien:
        md = stichprobe_markdown(pool["fragen"], kat, n=args.n, seed=args.seed)
        (ziel / f"{kat}.md").write_text(md + "\n", encoding="utf-8")
        print(md)
        print()
    print(f"Gespeichert in {ziel}/", file=sys.stderr)
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    pool = output.lade_pool()
    c = Counter((f["kategorie"], f["quelle_typ"]) for f in pool["fragen"])
    for kat in KATEGORIEN:
        wd, wp = c[(kat, "wikidata")], c[(kat, "wikipedia")]
        print(f"{KATEGORIEN[kat]:32} {wd + wp:5}  (wikidata {wd}, wikipedia {wp})")
    print(f"{'Total':32} {len(pool['fragen']):5}  generiert {pool['generiert_am']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wikiquiz-gen", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="Fragen erzeugen")
    g.add_argument("--kategorie", action="append", choices=list(KATEGORIEN))
    g.add_argument("--quelle", choices=["wikidata", "wikipedia", "alle"], default="wikidata")
    g.add_argument("--ziel", type=int, default=200, help="max. Fragen pro Kategorie und Quelle")
    g.add_argument("--min-sitelinks", type=int)
    g.add_argument("--min-pageviews", type=float)
    g.add_argument("--min-pageviews-antwort", type=float)
    g.add_argument("--min-zeichen", type=int)
    g.add_argument("--pageviews-exakt", action="store_true",
                   help="12-Monats-Werte für alle Kandidaten (sonst nur im Graubereich)")
    g.add_argument("--max-kandidaten", type=int, default=300, help="pro Template aus SPARQL")
    g.add_argument("--modus", choices=["ersetzen", "ergaenzen"], default="ersetzen")
    g.add_argument("--seed", type=int, default=42)
    g.add_argument("--dry-run", action="store_true", help="nichts schreiben, Stichprobe ausgeben")
    g.add_argument("--stichprobe", type=int, default=30)
    g.add_argument("--nur-cache", action="store_true", help="keine Netzwerkzugriffe")
    g.set_defaults(func=cmd_generate)

    r = sub.add_parser("review", help="Markdown-Stichprobe aus questions.json")
    r.add_argument("--kategorie", action="append", choices=list(KATEGORIEN))
    r.add_argument("--n", type=int, default=30)
    r.add_argument("--seed", type=int, default=1)
    r.set_defaults(func=cmd_review)

    s = sub.add_parser("stats", help="Anzahl Fragen pro Kategorie")
    s.set_defaults(func=cmd_stats)

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
