#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BaseMoneyAgent — Basisklasse fuer alle Geld-Recherche-Agenten.

Pattern: Observe → Search → Score → Report
Jeder Agent spezialisiert sich auf eine Kategorie und liefert MoneyIdea-Objekte.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
UTC = timezone.utc
from pathlib import Path
from typing import Any

log = logging.getLogger("CashMashine.Agent")

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class MoneyIdea:
    """Eine konkrete Geld-Idee von einem Agenten."""
    agent_name: str
    category: str           # survey | airdrop | gift | cashback | passive | gig
    title: str
    description: str
    url: str = ""
    effort_hours: float = 1.0       # Stunden bis zum ersten Euro
    monthly_potential_eur: float = 0.0  # Realistisches Monatspotenzial
    reliability: float = 0.5        # 0.0 = Scam-Risiko, 1.0 = sicher
    speed: float = 0.5              # 0.0 = langsam, 1.0 = sofortiger Cashout
    requirements: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    raw_score: float = 0.0          # Wird von scorer.py gesetzt
    found_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MoneyIdea":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class BaseMoneyAgent:
    """
    Basisklasse. Jeder Spezialist erbt hiervon und implementiert:
    - category: str
    - system_prompt: str
    - _search_web(): optionale Websuche
    - _parse_ideas(llm_response): MoneyIdea-Liste
    """

    category: str = "generic"
    system_prompt: str = "Du bist ein Experte fuer Online-Geldverdienen."
    search_queries: list[str] = []
    max_ideas: int = 5

    def __init__(self, openai_client, config: dict):
        self.client = openai_client
        self.config = config
        self.model = config.get("model", "gpt-4o-mini")
        self.name = f"{self.category.upper()}-Agent"
        self._ideas: list[MoneyIdea] = []
        self._start_time: float = 0.0
        self._duration: float = 0.0
        self._status: str = "idle"  # idle | running | done | error

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def run(self) -> list[MoneyIdea]:
        """Hauptmethode: Sucht Ideen und gibt sie zurueck."""
        self._start_time = time.time()
        self._status = "running"
        log.info(f"[{self.name}] START — suche nach {self.category}-Moeglichkeiten")
        try:
            web_context = await self._search_web()
            ideas = await self._query_llm(web_context)
            self._ideas = ideas
            self._status = "done"
            self._duration = time.time() - self._start_time
            log.info(f"[{self.name}] FERTIG — {len(ideas)} Ideen in {self._duration:.1f}s")
            return ideas
        except Exception as e:
            self._status = "error"
            self._duration = time.time() - self._start_time
            log.error(f"[{self.name}] FEHLER: {e}")
            return []

    def snapshot(self) -> dict:
        """Aktueller Status fuer Control Center."""
        return {
            "name": self.name,
            "category": self.category,
            "status": self._status,
            "ideas_found": len(self._ideas),
            "duration_s": round(self._duration, 2),
            "top_idea": self._ideas[0].title if self._ideas else None,
        }

    # ------------------------------------------------------------------ #
    # Internals — koennen von Subklassen ueberschrieben werden             #
    # ------------------------------------------------------------------ #

    async def _search_web(self) -> str:
        """Optionale Websuche. Standard: leer (nur LLM-Wissen)."""
        return ""

    async def _query_llm(self, web_context: str) -> list[MoneyIdea]:
        """Fragt OpenAI nach Ideen in dieser Kategorie."""
        context_block = f"\n\nAktuelle Web-Recherche:\n{web_context}" if web_context else ""
        user_prompt = self._build_user_prompt() + context_block

        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )
        raw = response.choices[0].message.content
        return self._parse_ideas(raw)

    def _build_user_prompt(self) -> str:
        return f"""Recherchiere die besten aktuellen Moeglichkeiten um Geld zu verdienen in der Kategorie: {self.category}

Antworte NUR mit einem JSON-Objekt in diesem Format:
{{
  "ideas": [
    {{
      "title": "Name der Moeglichkeit",
      "description": "Detaillierte Beschreibung (3-5 Saetze)",
      "url": "https://...",
      "effort_hours": 2.0,
      "monthly_potential_eur": 50.0,
      "reliability": 0.8,
      "speed": 0.7,
      "requirements": ["Anforderung 1", "Anforderung 2"],
      "steps": ["Schritt 1", "Schritt 2", "Schritt 3"],
      "tags": ["tag1", "tag2"]
    }}
  ]
}}

Finde genau {self.max_ideas} realistische, aktuell verfuegbare Moeglichkeiten.
Beruecksichtige: Deutschland/EU, 2025/2026, echte Verdienstmoeglichkeiten.
Monatliches Potenzial = realistischer Durchschnitt (kein Best-Case).
reliability: 1.0 = 100% sicher, 0.0 = hohes Scam-Risiko.
speed: 1.0 = Geld sofort verfuegbar, 0.0 = Monate bis zur Auszahlung."""

    def _parse_ideas(self, raw: str) -> list[MoneyIdea]:
        """Parst LLM-Response zu MoneyIdea-Objekten."""
        try:
            data = json.loads(raw)
            ideas = []
            for item in data.get("ideas", [])[:self.max_ideas]:
                idea = MoneyIdea(
                    agent_name=self.name,
                    category=self.category,
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    url=item.get("url", ""),
                    effort_hours=float(item.get("effort_hours", 1.0)),
                    monthly_potential_eur=float(item.get("monthly_potential_eur", 0.0)),
                    reliability=min(1.0, max(0.0, float(item.get("reliability", 0.5)))),
                    speed=min(1.0, max(0.0, float(item.get("speed", 0.5)))),
                    requirements=item.get("requirements", []),
                    steps=item.get("steps", []),
                    tags=item.get("tags", []),
                )
                ideas.append(idea)
            return ideas
        except Exception as e:
            log.error(f"[{self.name}] Parse-Fehler: {e}\nRaw: {raw[:200]}")
            return []
