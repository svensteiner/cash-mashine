#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Layer3 Platform Client — Scraping der Quest-Seite.

Layer3 hat keine offene API, daher Playwright-Scraping.
URL: https://layer3.xyz/quests
"""
from __future__ import annotations
import json, logging, time
from dataclasses import dataclass, field
from pathlib import Path
import requests
from bs4 import BeautifulSoup

log = logging.getLogger("Airdrop.Layer3")

QUESTS_URL = "https://layer3.xyz/quests"
CACHE_FILE = Path(__file__).parent.parent / "state" / "layer3_cache.json"
CACHE_TTL  = 600


@dataclass
class Layer3Quest:
    id: str
    name: str
    url: str
    reward: str = ""
    tasks: list[dict] = field(default_factory=list)
    automatable: bool = False


class Layer3Client:
    def __init__(self):
        self._cache: dict = {}

    def get_active_quests(self, limit: int = 15) -> list[Layer3Quest]:
        raw_html = self._fetch_html()
        if not raw_html:
            return []
        return self._parse_quests(raw_html, limit)

    def _fetch_html(self) -> str:
        now = time.time()
        if self._cache.get("ts", 0) + CACHE_TTL > now:
            return self._cache.get("html", "")
        if CACHE_FILE.exists():
            try:
                disk = json.loads(CACHE_FILE.read_text())
                if disk.get("ts", 0) + CACHE_TTL > now:
                    self._cache = disk
                    return disk.get("html", "")
            except Exception:
                pass
        try:
            resp = requests.get(
                QUESTS_URL,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            resp.raise_for_status()
            html = resp.text
            self._cache = {"ts": now, "html": html}
            CACHE_FILE.parent.mkdir(exist_ok=True)
            CACHE_FILE.write_text(json.dumps(self._cache))
            log.info("Layer3: Quest-Seite geladen.")
            return html
        except Exception as e:
            log.error(f"Layer3 fetch: {e}")
            return ""

    def _parse_quests(self, html: str, limit: int) -> list[Layer3Quest]:
        """Parst Layer3 Quest-Liste aus HTML (Next.js JSON embedded)."""
        quests = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            # Layer3 embeds data in <script id="__NEXT_DATA__">
            script = soup.find("script", {"id": "__NEXT_DATA__"})
            if script and script.string:
                data = json.loads(script.string)
                # Navigiere durch die Next.js Datenstruktur
                quests_data = (
                    data.get("props", {})
                    .get("pageProps", {})
                    .get("quests", [])
                )
                for q in quests_data[:limit]:
                    quests.append(Layer3Quest(
                        id          = str(q.get("id", "")),
                        name        = q.get("title", q.get("name", "?")),
                        url         = f"https://layer3.xyz/quests/{q.get('slug', q.get('id', ''))}",
                        reward      = str(q.get("reward", "")),
                        automatable = False,  # Layer3 braucht meist On-Chain-Aktionen
                    ))
                log.info(f"Layer3: {len(quests)} Quests geparst.")
        except Exception as e:
            log.debug(f"Layer3 parse: {e}")
        return quests
