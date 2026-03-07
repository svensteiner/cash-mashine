#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CashbackAgent — Findet die besten Cashback, Rewards und Bonusprogramme."""

from __future__ import annotations
import asyncio
import logging
import requests
from bs4 import BeautifulSoup
from .base_agent import BaseMoneyAgent

log = logging.getLogger("CashMashine.CashbackAgent")

CASHBACK_SITES = [
    "https://www.shoop.de/cashback",
    "https://www.igraal.de",
]

class CashbackAgent(BaseMoneyAgent):
    category = "cashback"
    max_ideas = 6
    system_prompt = """Du bist ein Experte fuer Cashback-Programme, Kreditkarten-Rewards und Bonuspunkte.
Du kennst:
- Cashback-Portale (Shoop, iGraal, Payback, etc.) und ihre besten Deals
- Kreditkarten mit hohen Cashback-Saetzen (Amex, etc.)
- Girokonto-Wechselbonus-Strategien (Bank wechseln fuer 100-200 EUR Bonus)
- Shopping-Portale der Banken und Airlines
- Stacking: Mehrere Cashback-Ebenen gleichzeitig nutzen
- Aktuelle Sonderaktionen mit erhoehtem Cashback"""

    async def _search_web(self) -> str:
        snippets = []
        for url in CASHBACK_SITES:
            try:
                resp = await asyncio.to_thread(
                    requests.get, url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=8,
                )
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for tag in soup(["script", "style", "nav"]):
                        tag.decompose()
                    text = soup.get_text(separator=" ", strip=True)[:700]
                    snippets.append(f"{url}:\n{text}")
            except Exception as e:
                log.debug(f"Scrape {url}: {e}")
        return "\n\n".join(snippets) if snippets else ""

    def _build_user_prompt(self) -> str:
        base = super()._build_user_prompt()
        return base + """

Fuer Cashback-Ideen:
- Konkrete Cashback-Saetze nennen (z.B. "3% auf alle Online-Einkauefe")
- Girokonto-Wechsel-Bosse: Welche Banken zahlen aktuell die besten Praemien?
- Kreditkarten-Signup-Boni: Welche lohnen sich ohne Jahresgebuehr-Falle?
- 'Cashback-Stacking': Wie kombiniert man Portal + Kreditkarte + Payback?
- Realistische EUR-Ersparnis pro Monat bei normalen Ausgaben (1500 EUR/Monat Budget)"""
