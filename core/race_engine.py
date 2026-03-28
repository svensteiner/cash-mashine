#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RaceEngine — Das Herz der Cash Mashine.

Startet alle Agenten GLEICHZEITIG (asyncio), sammelt Ergebnisse,
zeigt Live-Fortschritt und ermittelt den Gewinner.

Race-Ablauf:
  1. START — Alle Agenten laufen parallel los
  2. FINISH — Ergebnisse werden gesammelt (auch partielle)
  3. SCORE — IdeaScorer bewertet alle Ideen
  4. DECIDE — CashBrain waehlt Gewinner + erstellt Plan
  5. REPORT — Ergebnisse werden angezeigt + gespeichert
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
UTC = timezone.utc
from pathlib import Path
from typing import Optional

from agents import (
    SurveyAgent, AirdropAgent, GiftAgent,
    CashbackAgent, PassiveAgent, GigAgent,
    MoneyIdea,
)
from core.scorer import IdeaScorer
from core.brain import CashBrain
from core.control_center import ControlCenter

log = logging.getLogger("CashMashine.Race")

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state"
RESULTS_FILE = STATE_DIR / "race_results.json"
IDEAS_FILE = STATE_DIR / "ideas.json"


class RaceEngine:
    """
    Orchestriert das Agenten-Rennen.
    Kann einmalig oder im Dauerlauf betrieben werden.
    """

    def __init__(self, openai_client, config: dict):
        self.client = openai_client
        self.config = config
        self.brain = CashBrain(openai_client, config)
        self.control_center = ControlCenter(STATE_DIR)
        self._all_ideas: list[MoneyIdea] = []
        self._race_number = self._load_race_count()

    def _load_race_count(self) -> int:
        try:
            if RESULTS_FILE.exists():
                data = json.loads(RESULTS_FILE.read_text())
                return data.get("total_races", 0) + 1
        except Exception:
            pass
        return 1

    # ------------------------------------------------------------------ #
    # Main Race                                                            #
    # ------------------------------------------------------------------ #

    async def run_race(self) -> dict:
        """Fuehrt ein komplettes Rennen durch. Gibt Entscheidungs-Dict zurueck."""
        self._race_number = self._load_race_count()
        start = time.time()
        print(f"\n{'='*65}")
        print(f"  CASH MASHINE -- RENNEN #{self._race_number}")
        print(f"  Start: {datetime.now().strftime('%H:%M:%S')} | {len(self._build_agents())} Agenten")
        print(f"{'='*65}\n")

        # Phase 1: Alle Agenten parallel starten
        agents = self._build_agents()
        self.control_center.register_agents([a.name for a in agents])
        print("  [RENNEN] Alle Agenten gestartet — suchen parallel...\n")

        results = await self._run_agents_parallel(agents)

        # Phase 2: Ergebnisse sammeln
        all_ideas: list[MoneyIdea] = []
        for agent, ideas in results.items():
            all_ideas.extend(ideas)
            self.control_center.update_agent(agent, "done", len(ideas))

        self._all_ideas = all_ideas
        duration = time.time() - start
        print(f"\n  [FINISH] {len(all_ideas)} Ideen gesammelt in {duration:.1f}s")

        if not all_ideas:
            log.error("Keine Ideen gefunden — Rennen abgebrochen.")
            return {}

        # Phase 3: Scoring
        print("\n  [SCORING] Bewerte alle Ideen...")
        ranked = IdeaScorer.score_all(all_ideas)
        print(IdeaScorer.rank_summary(ranked, top_n=10))

        # Phase 4: Brain-Entscheidung
        print("\n  [BRAIN] Waehle beste Idee und erstelle Umsetzungsplan...")
        meta = {"race_number": self._race_number, "duration_s": round(duration, 2), "total_ideas": len(all_ideas)}
        decision = self.brain.decide(ranked, meta)

        # Phase 5: Speichern + Report
        self._save_results(ranked, decision, meta)
        self._print_winner(decision)

        return decision

    # ------------------------------------------------------------------ #
    # Parallel Execution                                                   #
    # ------------------------------------------------------------------ #

    async def _run_agents_parallel(self, agents: list) -> dict[str, list[MoneyIdea]]:
        """Alle Agenten gleichzeitig starten, Ergebnisse sammeln."""
        tasks = {agent.name: asyncio.create_task(agent.run()) for agent in agents}
        results = {}
        done_count = 0
        total = len(tasks)

        for coro in asyncio.as_completed(tasks.values()):
            ideas = await coro
            done_count += 1
            # Finde den Agenten der fertig wurde
            for name, task in tasks.items():
                if task.done() and name not in results:
                    results[name] = ideas
                    status = "OK" if ideas else "!!"
                    print(f"  [{status}] [{done_count}/{total}] {name}: {len(ideas)} Ideen")
                    break

        return results

    def _build_agents(self) -> list:
        cfg = self.config
        return [
            SurveyAgent(self.client, cfg),
            AirdropAgent(self.client, cfg),
            GiftAgent(self.client, cfg),
            CashbackAgent(self.client, cfg),
            PassiveAgent(self.client, cfg),
            GigAgent(self.client, cfg),
        ]

    # ------------------------------------------------------------------ #
    # Output                                                               #
    # ------------------------------------------------------------------ #

    def _print_winner(self, decision: dict) -> None:
        winner = decision.get("winner", {})
        plan = decision.get("plan", {})
        if not winner:
            return

        print(f"\n{'='*65}")
        print(f"  GEWINNER: {winner.get('title', '?')}")
        print(f"  Kategorie: {winner.get('category', '?').upper()}")
        print(f"  Score: {winner.get('raw_score', 0):.3f}")
        print(f"  Potenzial: ~{winner.get('monthly_potential_eur', 0):.0f} EUR/Monat")
        print(f"{'='*65}")
        print(f"\n  UMSETZUNGSPLAN:")
        print(f"  {plan.get('summary', '')}")
        print(f"\n  TAG 1 — Aktionen:")
        for action in plan.get("day1_actions", [])[:5]:
            print(f"    • {action}")
        print(f"\n  Erster Euro erwartet in: ~{plan.get('estimated_first_euro_days', '?')} Tagen")
        print(f"  Ziel nach Monat 1: {plan.get('month1_target_eur', 0):.0f} EUR")
        print(f"\n  Vollstaendiger Plan gespeichert in: state/brain_state.json")
        print(f"{'='*65}\n")

    def _save_results(self, ranked: list[MoneyIdea], decision: dict, meta: dict) -> None:
        STATE_DIR.mkdir(exist_ok=True)

        # Alle Ideen speichern
        ideas_data = [i.to_dict() for i in ranked]
        IDEAS_FILE.write_text(json.dumps(ideas_data, ensure_ascii=False, indent=2))

        # Rennen-Ergebnisse
        results = {
            "total_races": self._race_number,
            "last_race": {
                "timestamp": datetime.now(UTC).isoformat(),
                **meta,
                "top5": [i.to_dict() for i in ranked[:5]],
                "winner": decision.get("winner", {}),
            }
        }
        # Bestehende Ergebnisse laden und mergen
        try:
            if RESULTS_FILE.exists():
                existing = json.loads(RESULTS_FILE.read_text())
                history = existing.get("history", [])
            else:
                history = []
        except Exception:
            history = []

        history.append(results["last_race"])
        results["history"] = history[-10:]  # Nur letzte 10 Rennen behalten
        RESULTS_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2))
        log.info(f"Rennen #{self._race_number} Ergebnisse gespeichert.")
