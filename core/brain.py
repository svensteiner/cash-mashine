#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CashBrain — Entscheidungs-Gehirn der Cash Mashine.

Pattern: Observe → Decide → Implement → Reflect → Adapt
(Inspiriert vom SessionBrain des MarketingBots)

Aufgaben:
1. Analysiert alle Agenten-Ergebnisse
2. Waehlt die beste Idee aus
3. Erstellt einen konkreten Umsetzungsplan
4. Lernt aus vorherigen Runden
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("CashMashine.Brain")

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "state" / "brain_state.json"
HISTORY_FILE = ROOT / "state" / "implementation_history.json"


class CashBrain:
    """
    Entscheidungs-Gehirn: Waehlt die beste Idee und plant die Umsetzung.
    Lernt aus vorherigen Entscheidungen (Cross-Session Memory).
    """

    def __init__(self, openai_client, config: dict):
        self.client = openai_client
        self.config = config
        self.model = config.get("model_brain", config.get("model", "gpt-4o"))
        self._state: dict = self._load_state()
        self._history: list = self._load_history()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def decide(self, ranked_ideas: list, race_meta: dict) -> dict:
        """
        Hauptentscheidung: Welche Idee wird umgesetzt?
        Gibt den vollstaendigen Umsetzungsplan zurueck.
        """
        if not ranked_ideas:
            log.warning("Keine Ideen zum Entscheiden — Brain gibt Nothing zurueck.")
            return {}

        top3 = ranked_ideas[:3]
        winner = self._pick_winner(top3, race_meta)
        plan = self._create_implementation_plan(winner)
        self._save_decision(winner, plan, race_meta)
        return {"winner": winner.to_dict(), "plan": plan}

    def reflect(self, decision: dict, outcome: str = "pending") -> dict:
        """
        Reflect-Phase: Was lief gut/schlecht?
        Wird nach Umsetzung aufgerufen.
        """
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "winner_title": decision.get("winner", {}).get("title", ""),
            "winner_category": decision.get("winner", {}).get("category", ""),
            "winner_score": decision.get("winner", {}).get("raw_score", 0),
            "outcome": outcome,
        }
        self._history.append(entry)
        self._save_history()
        log.info(f"Brain Reflect: {entry['winner_title']} → {outcome}")
        return entry

    def get_avoidance_hints(self) -> list[str]:
        """Gibt Hinweise was man vermeiden soll (aus Geschichte gelernt)."""
        failed = [h["winner_category"] for h in self._history if h.get("outcome") == "failed"]
        if not failed:
            return []
        from collections import Counter
        counts = Counter(failed)
        return [f"Kategorie '{cat}' hatte {n} Fehlschlaege" for cat, n in counts.most_common(3)]

    # ------------------------------------------------------------------ #
    # Internals                                                            #
    # ------------------------------------------------------------------ #

    def _pick_winner(self, top3: list, race_meta: dict) -> Any:
        """Waehlt Gewinner — priorisiert nach Score, aber vermeidet bekannte Fehlschlaege."""
        avoid = self.get_avoidance_hints()
        failed_cats = {h["winner_category"] for h in self._history if h.get("outcome") == "failed"}

        for idea in top3:
            if idea.category not in failed_cats:
                return idea
        # Falls alle Top-3 aus problematischen Kategorien kommen: nimm trotzdem den Besten
        return top3[0]

    def _create_implementation_plan(self, winner: Any) -> dict:
        """Erstellt einen konkreten Schritt-fuer-Schritt Umsetzungsplan via LLM."""
        idea_json = json.dumps(winner.to_dict(), ensure_ascii=False, indent=2)
        avoid_hints = self.get_avoidance_hints()
        avoid_block = f"\n\nZu vermeiden (aus Erfahrung):\n" + "\n".join(avoid_hints) if avoid_hints else ""

        prompt = f"""Du bist ein Umsetzungs-Coach. Erstelle einen konkreten Aktionsplan fuer diese Geld-Idee:

{idea_json}{avoid_block}

Antworte NUR mit einem JSON-Objekt:
{{
  "title": "Umsetzungsplan: {{idea.title}}",
  "summary": "2-3 Saetze Zusammenfassung",
  "day1_actions": ["Aktion 1 (konkret, heute machbar)", "Aktion 2", "Aktion 3"],
  "week1_goals": ["Ziel 1", "Ziel 2"],
  "month1_target_eur": 50.0,
  "tools_needed": ["Tool/Account 1", "Tool 2"],
  "pitfalls": ["Haeufiger Fehler 1", "Haeufiger Fehler 2"],
  "success_metric": "Woran erkennt man Erfolg?",
  "automation_potential": "Wie kann man es automatisieren?",
  "estimated_first_euro_days": 7
}}

Sei konkret, realistisch und auf Deutschland ausgerichtet."""

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du bist ein pragmatischer Business-Coach. Antworte immer auf Deutsch."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.5,
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            log.error(f"Plan-Erstellung fehlgeschlagen: {e}")
            # Fallback: Daten direkt aus der Idee verwenden
            return {
                "title": f"Plan: {winner.title}",
                "summary": winner.description[:300] if winner.description else "",
                "day1_actions": winner.steps[:5] if winner.steps else ["Recherche starten", "Account anlegen", "Erste Aktion durchfuehren"],
                "week1_goals": [f"Erste {winner.monthly_potential_eur/4:.0f} EUR verdienen"],
                "month1_target_eur": winner.monthly_potential_eur,
                "tools_needed": winner.requirements[:3] if winner.requirements else [],
                "pitfalls": [],
                "success_metric": f"Erste EUR innerhalb von {int(winner.effort_hours)} Stunden",
                "automation_potential": "Noch nicht definiert",
                "estimated_first_euro_days": max(1, int(winner.effort_hours / 2)),
            }

    def _save_decision(self, winner: Any, plan: dict, meta: dict) -> None:
        self._state = {
            "last_decision_at": datetime.now(UTC).isoformat(),
            "winner": winner.to_dict(),
            "plan": plan,
            "race_meta": meta,
        }
        STATE_FILE.parent.mkdir(exist_ok=True)
        STATE_FILE.write_text(json.dumps(self._state, ensure_ascii=False, indent=2))
        log.info(f"Brain Entscheidung gespeichert: {winner.title}")

    def _load_state(self) -> dict:
        try:
            if STATE_FILE.exists():
                return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
        return {}

    def _save_history(self) -> None:
        HISTORY_FILE.parent.mkdir(exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(self._history, ensure_ascii=False, indent=2))

    def _load_history(self) -> list:
        try:
            if HISTORY_FILE.exists():
                data = json.loads(HISTORY_FILE.read_text())
                return data if isinstance(data, list) else []
        except Exception:
            pass
        return []
