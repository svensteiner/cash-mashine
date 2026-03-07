#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PassiveAgent — Recherchiert passive Einkommensquellen und semi-passive Modelle."""

from __future__ import annotations
import logging
from .base_agent import BaseMoneyAgent

log = logging.getLogger("CashMashine.PassiveAgent")


class PassiveAgent(BaseMoneyAgent):
    category = "passive"
    max_ideas = 5
    system_prompt = """Du bist ein Experte fuer passives und semi-passives Einkommen.
Du kennst realistische Moeglichkeiten (kein Betrug, kein Get-Rich-Quick):
- Dividenden-Investitionen (ETFs, REITs)
- P2P-Lending Plattformen (Risiken beachten!)
- Digitale Produkte verkaufen (Templates, Presets, eBooks)
- Print-on-Demand (Merch by Amazon, Redbubble)
- Affiliate Marketing fuer eigene Seiten/Kanaele
- High-Yield Savings / Tagesgeld
- Lizenzierung von Fotos/Musik
- Nodes betreiben (Crypto)
Sei realistisch: Echter Aufwand anfangs, dann passiv."""

    def _build_user_prompt(self) -> str:
        base = super()._build_user_prompt()
        return base + """

Fuer passive Einkommens-Ideen:
- Realistischer Setup-Aufwand (effort_hours = Stunden bis es laeuft)
- Monatliches Potenzial nach 3 Monaten Aufbau
- Minimales Startkapital nennen (falls noetig)
- Steuerliche Hinweise fuer Deutschland
- Skalierbarkeit: Kann man es ausbauen?
- Zeitaufwand nach Setup: Stunden pro Woche"""
