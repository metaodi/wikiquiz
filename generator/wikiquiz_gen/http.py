"""HTTP-Client mit User-Agent, Rate-Limit pro Host, Retry und SQLite-Cache.

Wiederholte Läufe lesen aus dem Cache und belasten die Wikimedia-APIs nicht erneut.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

import requests

from .config import CACHE_DIR, USER_AGENT

log = logging.getLogger(__name__)

# Minimaler Abstand zwischen zwei Requests pro Host (Sekunden)
HOST_INTERVALL = {
    "query.wikidata.org": 1.0,  # SPARQL: seriell und zurückhaltend
    "www.wikidata.org": 0.2,
    "de.wikipedia.org": 0.1,
    "wikimedia.org": 0.25,  # Pageviews-API (drosselt bei Parallelität mit 429)
}
STANDARD_INTERVALL = 0.2
TAG = 86400


class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._naechster: dict[str, float] = {}

    def warte(self, host: str) -> None:
        intervall = HOST_INTERVALL.get(host, STANDARD_INTERVALL)
        with self._lock:
            jetzt = time.monotonic()
            start = max(jetzt, self._naechster.get(host, 0.0))
            self._naechster[host] = start + intervall
        if start > jetzt:
            time.sleep(start - jetzt)

    def sperre(self, host: str, sekunden: float) -> None:
        """Nach HTTP 429: Host für alle Threads pausieren."""
        with self._lock:
            self._naechster[host] = max(self._naechster.get(host, 0.0), time.monotonic() + sekunden)


class Http:
    def __init__(self, cache_pfad: Path | None = None, nur_cache: bool = False) -> None:
        cache_pfad = cache_pfad or CACHE_DIR / "http.sqlite"
        cache_pfad.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(cache_pfad, check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS cache (schluessel TEXT PRIMARY KEY, url TEXT,"
            " status INTEGER, body TEXT, zeit REAL)"
        )
        self._db_lock = threading.Lock()
        self._limiter = RateLimiter()
        self._local = threading.local()
        self.nur_cache = nur_cache
        self.stats = {"cache": 0, "netz": 0}

    def _session(self) -> requests.Session:
        s = getattr(self._local, "session", None)
        if s is None:
            s = requests.Session()
            s.headers.update(
                {"User-Agent": USER_AGENT, "Api-User-Agent": USER_AGENT, "Accept": "application/json"}
            )
            self._local.session = s
        return s

    @staticmethod
    def _schluessel(methode: str, url: str, params: dict | None, daten: dict | None) -> str:
        roh = json.dumps([methode, url, params or {}, daten or {}], sort_keys=True)
        return hashlib.sha256(roh.encode()).hexdigest()

    def _cache_lesen(self, schluessel: str, ttl: float) -> tuple[int, str] | None:
        with self._db_lock:
            row = self._db.execute(
                "SELECT status, body, zeit FROM cache WHERE schluessel=?", (schluessel,)
            ).fetchone()
        if row and (self.nur_cache or time.time() - row[2] < ttl):
            return row[0], row[1]
        return None

    def _cache_schreiben(self, schluessel: str, url: str, status: int, body: str) -> None:
        with self._db_lock:
            self._db.execute(
                "INSERT OR REPLACE INTO cache VALUES (?,?,?,?,?)",
                (schluessel, url, status, body, time.time()),
            )
            self._db.commit()

    def json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        daten: dict[str, Any] | None = None,
        ttl: float = 30 * TAG,
        versuche: int = 8,
    ) -> Any | None:
        """GET (oder POST mit `daten`) und JSON zurückgeben. 404 → None (wird gecacht)."""
        methode = "POST" if daten is not None else "GET"
        schluessel = self._schluessel(methode, url, params, daten)
        treffer = self._cache_lesen(schluessel, ttl)
        if treffer is not None:
            self.stats["cache"] += 1
            status, body = treffer
            return None if status == 404 else json.loads(body)
        if self.nur_cache:
            raise RuntimeError(f"Nicht im Cache (nur_cache): {url}")

        host = urlparse(url).hostname or ""
        anzeige = url + ("?" + urlencode(params) if params else "")
        for versuch in range(versuche):
            self._limiter.warte(host)
            try:
                r = self._session().request(methode, url, params=params, data=daten, timeout=90)
            except requests.RequestException as e:
                pause = 2**versuch
                log.warning("Netzwerkfehler %s (%s), neuer Versuch in %ss", anzeige[:120], e, pause)
                time.sleep(pause)
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                pause = float(r.headers.get("Retry-After") or 2**versuch)
                pause = min(max(pause, 2**versuch), 120)
                log.warning("HTTP %s für %s, warte %ss", r.status_code, anzeige[:100], pause)
                self._limiter.sperre(host, pause)
                continue
            self.stats["netz"] += 1
            if r.status_code == 404:
                self._cache_schreiben(schluessel, anzeige, 404, "")
                return None
            r.raise_for_status()
            self._cache_schreiben(schluessel, anzeige, r.status_code, r.text)
            return r.json()
        raise RuntimeError(f"Request nach {versuche} Versuchen fehlgeschlagen: {anzeige[:200]}")
