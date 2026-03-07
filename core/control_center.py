#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ControlCenter — Live-Dashboard fuer das Agenten-Rennen.
(Inspiriert vom AgenticControlCenter des MarketingBots)

Zeigt Echtzeit-Status aller Agenten, aktuelle Scores,
Gewinner-Historie und System-Health.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, UTC
from pathlib import Path

log = logging.getLogger("CashMashine.ControlCenter")

CC_FILE_NAME = "control_center.json"


class ControlCenter:
    """Aggregiert und persistiert den Status aller laufenden Agenten."""

    def __init__(self, state_dir: Path):
        self._state_dir = state_dir
        self._file = state_dir / CC_FILE_NAME
        self._agents: dict[str, dict] = {}
        self._load()

    def register_agents(self, names: list[str]) -> None:
        """Registriert Agenten zu Beginn eines Rennens."""
        self._agents = {
            name: {"status": "running", "ideas_found": 0, "top_idea": None}
            for name in names
        }
        self._save()

    def update_agent(self, name: str, status: str, ideas_count: int) -> None:
        if name in self._agents:
            self._agents[name]["status"] = status
            self._agents[name]["ideas_found"] = ideas_count
        self._save()

    def get_snapshot(self) -> dict:
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "agents": self._agents,
            "total_ideas": sum(a["ideas_found"] for a in self._agents.values()),
            "agents_done": sum(1 for a in self._agents.values() if a["status"] == "done"),
            "agents_total": len(self._agents),
        }

    def print_dashboard(self, race_results_file: Path | None = None) -> None:
        """Gibt das Control-Center-Dashboard auf der Konsole aus."""
        snap = self.get_snapshot()
        print(f"\n{'─'*60}")
        print(f"  CONTROL CENTER — {snap['timestamp'][:19]}")
        print(f"  Agenten: {snap['agents_done']}/{snap['agents_total']} fertig | "
              f"Ideen: {snap['total_ideas']}")
        print(f"{'─'*60}")
        for name, info in snap["agents"].items():
            icon = "✓" if info["status"] == "done" else "⟳" if info["status"] == "running" else "✗"
            print(f"  {icon} {name:<25} {info['ideas_found']:>3} Ideen")

        # Letzte Gewinner aus Race-History
        if race_results_file and race_results_file.exists():
            try:
                data = json.loads(race_results_file.read_text())
                history = data.get("history", [])
                if history:
                    last = history[-1]
                    winner = last.get("winner", {})
                    print(f"\n  Letzter Gewinner: {winner.get('title', '?')[:45]}")
                    print(f"  Score: {winner.get('raw_score', 0):.3f} | "
                          f"~{winner.get('monthly_potential_eur', 0):.0f} EUR/Mo")
                    print(f"  Gesamtrennen: {data.get('total_races', 0)}")
            except Exception:
                pass
        print(f"{'─'*60}\n")

    def _save(self) -> None:
        try:
            self._state_dir.mkdir(exist_ok=True)
            self._file.write_text(json.dumps(self.get_snapshot(), ensure_ascii=False, indent=2))
        except Exception as e:
            log.debug(f"ControlCenter save: {e}")

    def _load(self) -> None:
        try:
            if self._file.exists():
                data = json.loads(self._file.read_text())
                self._agents = data.get("agents", {})
        except Exception:
            self._agents = {}
