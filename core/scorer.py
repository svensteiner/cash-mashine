#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IdeaScorer — Bewertet MoneyIdea-Objekte nach einem gewichteten Scoring-Modell.

Score-Formel:
  raw_score = (
      0.35 * earnings_score     # Monatliches Potenzial
    + 0.25 * reliability        # Vertrauenswuerdigkeit / Scam-Risiko
    + 0.20 * speed_to_money     # Wie schnell kommt Geld?
    + 0.20 * effort_efficiency  # EUR pro Stunde Aufwand
  )
"""

from __future__ import annotations
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.base_agent import MoneyIdea


# ------------------------------------------------------------------ #
# Scoring-Gewichte                                                     #
# ------------------------------------------------------------------ #
W_EARNINGS    = 0.35
W_RELIABILITY = 0.25
W_SPEED       = 0.20
W_EFFICIENCY  = 0.20

# Referenzwerte fuer Normalisierung
MAX_MONTHLY_EUR   = 500.0   # Alles drueber gibt max Earnings-Score
REFERENCE_EUR_H   = 20.0    # Ziel-Stundensatz (20 EUR/h = top)


class IdeaScorer:
    """Bewertet und sortiert Ideen nach Gesamtscore."""

    @staticmethod
    def score(idea: "MoneyIdea") -> float:
        """Berechnet den raw_score fuer eine Idee. Gibt Wert 0.0-1.0 zurueck."""
        earnings_score   = IdeaScorer._earnings_score(idea.monthly_potential_eur)
        reliability      = idea.reliability  # bereits 0.0-1.0
        speed            = idea.speed        # bereits 0.0-1.0
        efficiency       = IdeaScorer._efficiency_score(
            idea.monthly_potential_eur, idea.effort_hours
        )

        raw = (
            W_EARNINGS    * earnings_score +
            W_RELIABILITY * reliability +
            W_SPEED       * speed +
            W_EFFICIENCY  * efficiency
        )
        return round(min(1.0, max(0.0, raw)), 4)

    @staticmethod
    def _earnings_score(monthly_eur: float) -> float:
        """Logarithmische Normalisierung: 500 EUR/Monat = 1.0."""
        if monthly_eur <= 0:
            return 0.0
        return min(1.0, math.log1p(monthly_eur) / math.log1p(MAX_MONTHLY_EUR))

    @staticmethod
    def _efficiency_score(monthly_eur: float, effort_hours: float) -> float:
        """EUR/h normalisiert gegen Referenz-Stundensatz."""
        if effort_hours <= 0:
            return 0.0
        # Annahme: Aufwand ist pro Monat ca. 4x effort_hours fuer laufenden Betrieb
        monthly_hours = max(effort_hours, effort_hours * 4)
        eur_per_hour = monthly_eur / monthly_hours if monthly_hours > 0 else 0
        return min(1.0, eur_per_hour / REFERENCE_EUR_H)

    @staticmethod
    def score_all(ideas: list["MoneyIdea"]) -> list["MoneyIdea"]:
        """Berechnet Scores fuer alle Ideen und sortiert absteigend."""
        for idea in ideas:
            idea.raw_score = IdeaScorer.score(idea)
        return sorted(ideas, key=lambda i: i.raw_score, reverse=True)

    @staticmethod
    def rank_summary(ideas: list["MoneyIdea"], top_n: int = 10) -> str:
        """Erstellt eine lesbare Ranking-Tabelle."""
        ranked = IdeaScorer.score_all(ideas)[:top_n]
        lines = ["", "=" * 70, "  CASH MASHINE — IDEEN-RANKING", "=" * 70]
        for i, idea in enumerate(ranked, 1):
            medal = ["[1]", "[2]", "[3]"][i-1] if i <= 3 else f" {i}."
            lines.append(
                f"{medal} [{idea.category.upper():10}] {idea.title[:40]:<40} "
                f"Score: {idea.raw_score:.3f}  "
                f"~{idea.monthly_potential_eur:.0f} EUR/Mo"
            )
        lines.append("=" * 70)
        return "\n".join(lines)
