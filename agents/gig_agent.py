#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GigAgent — Findet Freelance, Gig-Economy und Task-basierte Verdienstmoeglichkeiten."""

from __future__ import annotations
import asyncio
import logging
import requests
from bs4 import BeautifulSoup
from .base_agent import BaseMoneyAgent

log = logging.getLogger("CashMashine.GigAgent")

GIG_SITES = [
    "https://www.fiverr.com/categories",
    "https://www.clickworker.com/de",
]

class GigAgent(BaseMoneyAgent):
    category = "gig"
    max_ideas = 6
    system_prompt = """Du bist ein Experte fuer die Gig-Economy und Freelance-Moeglichkeiten.
Du kennst:
- Micro-Task Plattformen (Clickworker, Amazon MTurk, Appen)
- Freelance-Marktplaetze (Fiverr, Upwork, 99designs)
- Lokale Gigs (TaskRabbit, Helpling, myHammer)
- KI-Daten-Annotation und Training (Scale AI, Remotasks)
- Virtuelle Assistenz
- Social Media Management als Freelancer
- Content Creation fuer Firmen
Fokus: Was kann man SOFORT starten, ohne Ausbildung/Zertifikat?"""

    async def _search_web(self) -> str:
        snippets = []
        for url in GIG_SITES:
            try:
                resp = await asyncio.to_thread(
                    requests.get, url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=8,
                )
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for tag in soup(["script", "style", "nav", "footer"]):
                        tag.decompose()
                    text = soup.get_text(separator=" ", strip=True)[:600]
                    snippets.append(f"{url}:\n{text}")
            except Exception as e:
                log.debug(f"Scrape {url}: {e}")
        return "\n\n".join(snippets) if snippets else ""

    def _build_user_prompt(self) -> str:
        base = super()._build_user_prompt()
        return base + """

Fuer Gig/Freelance-Ideen:
- Nur Moeglichkeiten die man ohne spezielle Vorkenntnisse starten kann
- Realistische Stundensaetze fuer Anfaenger
- Plattform-Gebuehren einrechnen
- 'Schnellste zum ersten Euro'-Ideen bevorzugen
- KI-nahe Tasks: Daten-Annotation, Prompt-Engineering, KI-Testen
- Lokale Gigs: Was ist in Deutschland gefragt?"""
