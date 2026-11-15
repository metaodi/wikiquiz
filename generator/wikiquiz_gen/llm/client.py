"""Dünner Wrapper um das Anthropic-SDK: strukturierte JSON-Ausgabe, Kostenzählung.

Konfiguration über Umgebungsvariablen:
  ANTHROPIC_API_KEY        API-Key (nur im Generator, nie im Client)
  WIKIQUIZ_GEN_MODEL       Modell für die Generierung (Standard: claude-opus-5-5)
  WIKIQUIZ_CHECK_MODEL     Modell für die Prüfung (Standard: wie Generierung)
  WIKIQUIZ_EFFORT          Denkaufwand low|medium|high (Standard: medium)
"""
from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field

import anthropic

log = logging.getLogger(__name__)

STANDARD_MODELL = "claude-opus-5-5"

# USD pro 1 Mio. Tokens (Eingabe, Ausgabe) – nur für die Kostenschätzung im Protokoll
PREISE = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-fable-5-2": (8.0, 40.0),
}


class LLMFehler(Exception):
    """Fehler bei einem einzelnen Aufruf; der Lauf geht mit dem nächsten Artikel weiter."""


class AnmeldeFehler(Exception):
    """Anmeldung bei Anthropic fehlgeschlagen (API-Key, Föderation); der Lauf wird abgebrochen."""


@dataclass
class Verbrauch:
    eingabe: int = 0
    ausgabe: int = 0
    aufrufe: int = 0
    kosten_usd: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def addieren(self, modell: str, usage) -> None:
        ein = (usage.input_tokens or 0) + (getattr(usage, "cache_read_input_tokens", 0) or 0) \
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
        aus = usage.output_tokens or 0
        p_ein, p_aus = PREISE.get(modell, (0.0, 0.0))
        with self._lock:
            self.eingabe += ein
            self.ausgabe += aus
            self.aufrufe += 1
            self.kosten_usd += ein / 1e6 * p_ein + aus / 1e6 * p_aus


class LLM:
    def __init__(self, modell: str, effort: str | None = None, verbrauch: Verbrauch | None = None) -> None:
        self.modell = modell
        self.effort = effort or os.environ.get("WIKIQUIZ_EFFORT", "medium")
        self.verbrauch = verbrauch or Verbrauch()
        self.client = anthropic.Anthropic(max_retries=4)

    @classmethod
    def generierung(cls, verbrauch: Verbrauch) -> "LLM":
        return cls(os.environ.get("WIKIQUIZ_GEN_MODEL", STANDARD_MODELL), verbrauch=verbrauch)

    @classmethod
    def pruefung(cls, verbrauch: Verbrauch) -> "LLM":
        modell = os.environ.get("WIKIQUIZ_CHECK_MODEL") or os.environ.get("WIKIQUIZ_GEN_MODEL", STANDARD_MODELL)
        return cls(modell, verbrauch=verbrauch)

    def pruefe_anmeldung(self) -> None:
        """Kostenloser Test vor dem Lauf: Anmeldung und Modellname prüfen (Models API)."""
        try:
            self.client.models.retrieve(self.modell)
        except anthropic.NotFoundError as e:
            raise AnmeldeFehler(f"Modell {self.modell!r} nicht gefunden") from e
        except anthropic.APIConnectionError as e:
            raise LLMFehler(f"Verbindungsfehler: {e}") from e
        except anthropic.APIStatusError as e:
            raise AnmeldeFehler(f"HTTP {e.status_code}: {e.message}") from e
        except anthropic.AnthropicError as e:
            raise AnmeldeFehler(str(e)) from e

    def json(self, nachricht: str, schema: dict, system: str | None = None, max_tokens: int = 16000) -> dict:
        """Ein Aufruf mit erzwungener JSON-Ausgabe nach `schema`."""
        params: dict = {
            "model": self.modell,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": nachricht}],
            "output_config": {"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
        }
        if system:
            params["system"] = system
        try:
            # Serverseitiger Fallback auf ein anderes Modell, falls ein Sicherheitsfilter ablehnt
            antwort = self.client.beta.messages.create(
                **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
            )
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            raise AnmeldeFehler(f"HTTP {e.status_code}: {e.message}") from e
        except anthropic.APIStatusError as e:
            raise LLMFehler(f"API-Fehler {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise LLMFehler(f"Verbindungsfehler: {e}") from e
        except anthropic.AnthropicError as e:  # z. B. fehlgeschlagener Token-Austausch (Föderation)
            raise AnmeldeFehler(str(e)) from e
        self.verbrauch.addieren(self.modell, antwort.usage)
        if antwort.stop_reason == "refusal":
            raise LLMFehler("Anfrage abgelehnt (refusal)")
        if antwort.stop_reason == "max_tokens":
            raise LLMFehler("Antwort abgeschnitten (max_tokens)")
        text = next((b.text for b in antwort.content if b.type == "text"), None)
        if text is None:
            raise LLMFehler("Keine Textantwort")
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMFehler(f"Ungültiges JSON: {e}") from e
