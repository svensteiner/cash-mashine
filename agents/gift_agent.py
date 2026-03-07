#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GiftAgent — Findet Gratis-Produkte, Freebies, Gewinnspiele und Proben."""

from __future__ import annotations
import asyncio
import logging
import requests
from bs4 import BeautifulSoup
from .base_agent import BaseMoneyAgent

log = logging.getLogger("CashMashine.GiftAgent")

FREEBIE_SITES = [
    "https://www.meinpunktekonto.de",
    "https://www.gratis-reise.de",
]

class GiftAgent(BaseMoneyAgent):
    category = "gift"
    max_ideas = 6
    system_prompt = """Du bist ein Experte fuer Gratis-Produkte, Freebies und Gutschein-Strategien.
Du kennst:
- Produkttest-Plattformen (Testerheld, Pinecone, etc.)
- Cashback-Deals wo Produkte effektiv kostenlos werden
- Gewinnspiele mit guten Chancen (wenig Teilnehmer)
- Rabattcodes und Willkommensangebote
- Newsletter-Anmeldebonus-Strategien
- Gratis-Proben von Firmen
Ziel: Kostenlose Produkte oder geldwerte Vorteile erhalten."""

    async def _search_web(self) -> str:
        snippets = []
        for url in FREEBIE_SITES:
            try:
                resp = await asyncio.to_thread(
                    requests.get, url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=8,
                )
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for tag in soup(["script", "style"]):
                        tag.decompose()
                    text = soup.get_text(separator=" ", strip=True)[:600]
                    snippets.append(text)
            except Exception as e:
                log.debug(f"Scrape {url}: {e}")
        return "\n".join(snippets) if snippets else ""

    def _build_user_prompt(self) -> str:
        base = super()._build_user_prompt()
        return base + """

Fuer Gift/Freebie-Ideen:
- Fokus auf Deutschland/EU
- Produkttest-Plattformen: Was zahlen sie? Wie oft gibt es Tests?
- Clever-Cashback: Produkte bei denen Cashback den Preis auf 0 EUR bringt
- Legale 'Willkommens-Bonusse' bei Bankkonten, Apps etc.
- Gratis-Streaming: Welche Dienste haben gratis Testmonate ohne Haken?
- Gewinnspiele: Wo ist das Chancen/Aufwand-Verhaeltnis gut?"""
