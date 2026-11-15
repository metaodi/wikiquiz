"""Review-Modus: lesbare Markdown-Stichprobe pro Kategorie."""
from __future__ import annotations

import random
from collections import Counter

from .config import KATEGORIEN


def stichprobe_markdown(fragen: list[dict], kategorie: str, n: int = 30, seed: int = 1) -> str:
    alle = [f for f in fragen if f["kategorie"] == kategorie]
    auswahl = random.Random(seed).sample(alle, min(n, len(alle)))
    schw = Counter(f["schwierigkeit"] for f in alle)
    quellen = Counter(f["quelle_typ"] for f in alle)
    zeilen = [
        f"# Stichprobe: {KATEGORIEN[kategorie]}",
        "",
        f"{len(auswahl)} von {len(alle)} Fragen · Schwierigkeit "
        + ", ".join(f"{k}: {schw[k]}" for k in (1, 2, 3))
        + " · Quellen "
        + ", ".join(f"{k}: {v}" for k, v in sorted(quellen.items())),
        "",
    ]
    for i, f in enumerate(auswahl, 1):
        richtig = f["antworten"][f["korrekt_index"]]
        falsch = [a for j, a in enumerate(f["antworten"]) if j != f["korrekt_index"]]
        zeilen += [
            f"{i}. **{f['frage']}**  ",
            f"   ✅ {richtig} · ❌ {' · '.join(falsch)}  ",
            f"   Schwierigkeit {f['schwierigkeit']} · [{f['quelle_titel']}]({f['quelle_url']}) "
            f"· {f['quelle_typ']} · `{f['id']}`",
            "",
        ]
    return "\n".join(zeilen)
