#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AirdropAgent — Recherchiert aktive Krypto-Airdrops und Token-Geschenke."""

from __future__ import annotations
import asyncio
import logging
import requests
from bs4 import BeautifulSoup
from .base_agent import BaseMoneyAgent

log = logging.getLogger("CashMashine.AirdropAgent")

AIRDROP_SITES = [
    "https://airdropalert.com/airdrops",
    "https://airdrops.io",
]

class AirdropAgent(BaseMoneyAgent):
    category = "airdrop"
    max_ideas = 5
    system_prompt = """Du bist ein Krypto-Experte spezialisiert auf Token-Airdrops und DeFi-Rewards.
Du kennst die besten Strategien um kostenlos Token zu erhalten:
- Retroactive Airdrops (Protokolle nutzen bevor Airdrop announced wird)
- Testnet-Teilnahme
- Discord/Twitter-Quests
- Liquidity Mining Rewards
- NFT-Whitelists
Sei ehrlich ueber Risiken (Scams, Gas-Kosten, Steuer-Implikationen in DE)."""

    async def _search_web(self) -> str:
        """Scraped aktive Airdrop-Listen."""
        snippets = []
        for url in AIRDROP_SITES:
            try:
                resp = await asyncio.to_thread(
                    requests.get, url,
                    headers={"User-Agent": "Mozilla/5.0 (compatible)"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    # Extrahiere relevante Text-Chunks
                    for tag in soup(["script", "style", "nav", "footer"]):
                        tag.decompose()
                    text = soup.get_text(separator=" ", strip=True)[:800]
                    snippets.append(f"Quelle {url}:\n{text}")
            except Exception as e:
                log.debug(f"Scrape {url} fehlgeschlagen: {e}")
        return "\n\n".join(snippets) if snippets else ""

    def _build_user_prompt(self) -> str:
        base = super()._build_user_prompt()
        return base + """

Fuer Airdrop-Ideen:
- Nenne konkrete Protokolle/Projekte die JETZT gerade Airdrops haben oder bald haben werden
- Erklaere exakt: Was muss man tun? Wie viel Gas-Kosten? Wie viel Zeitaufwand?
- Scam-Risiko klar kennzeichnen (reliability < 0.5 = Vorsicht!)
- Auch 'Soft Airdrops': Galxe Quests, Layer3, Zealy-Kampagnen
- Retroactive Strategien: Welche Protokolle koennen noch einen Airdrop ankuendigen?"""
