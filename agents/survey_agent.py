#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SurveyAgent — Findet bezahlte Umfrage-Plattformen und Moeglichkeiten."""

from __future__ import annotations
import asyncio
import logging
import requests
from bs4 import BeautifulSoup
from .base_agent import BaseMoneyAgent

log = logging.getLogger("CashMashine.SurveyAgent")

SCRAPE_TARGETS = [
    ("https://www.surveytime.io", "SurveyTime"),
    ("https://www.prolific.com", "Prolific"),
]

class SurveyAgent(BaseMoneyAgent):
    category = "survey"
    max_ideas = 6
    system_prompt = """Du bist ein Experte fuer bezahlte Online-Umfragen und Market Research.
Du kennst alle grossen Umfrage-Plattformen, deren Auszahlungsraten, Mindestbetraege und Vertrauenswuerdigkeit.
Fokus: Deutschland/EU-verfuegbare Plattformen, echte Verdienstmoeglichkeiten 2025/2026.
Sei realistisch: Umfragen zahlen selten mehr als 3-6 EUR/Stunde."""

    async def _search_web(self) -> str:
        """Scraped oeffentliche Infos zu Umfrage-Plattformen."""
        snippets = []
        for url, name in SCRAPE_TARGETS:
            try:
                resp = await asyncio.to_thread(
                    requests.get, url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=8,
                )
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    text = soup.get_text(separator=" ", strip=True)[:500]
                    snippets.append(f"{name}: {text}")
            except Exception as e:
                log.debug(f"Scrape {name} fehlgeschlagen: {e}")
        return "\n\n".join(snippets) if snippets else ""

    def _build_user_prompt(self) -> str:
        base = super()._build_user_prompt()
        return base + """

Spezifische Anforderungen fuer Survey-Ideen:
- Nur seriose Plattformen (kein MLM, kein Pyramid-Scheme)
- Echte EUR-Auszahlung oder Amazon-Gutscheine
- Mindestens Trustpilot 3.5+
- Erklaere: Auszahlungsminimum, Auszahlungsweg (PayPal/Bank/etc)
- Bonus-Ideen: Fokusgruppen (zahlen bis 100 EUR/h), User-Testing (UserTesting, Testbirds)"""
