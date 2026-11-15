"""Wikidata-SPARQL-Client."""
from __future__ import annotations

from urllib.parse import quote, unquote

from .http import TAG, Http

ENDPOINT = "https://query.wikidata.org/sparql"
DE_WIKI = "https://de.wikipedia.org/wiki/"


def abfrage(http: Http, sparql: str, ttl: float = 7 * TAG) -> list[dict[str, str]]:
    """Führt eine SPARQL-Abfrage aus und gibt Zeilen als {variable: wert} zurück."""
    res = http.json(ENDPOINT, daten={"query": sparql, "format": "json"}, ttl=ttl)
    zeilen = []
    for b in res["results"]["bindings"]:
        zeilen.append({k: v["value"] for k, v in b.items()})
    return zeilen


def qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def titel_aus_url(url: str) -> str:
    """https://de.wikipedia.org/wiki/K%C3%B6ln → 'Köln'"""
    return unquote(url.removeprefix(DE_WIKI)).replace("_", " ")


def artikel_url(titel: str) -> str:
    return DE_WIKI + quote(titel.replace(" ", "_"), safe=":/(),'!*")
