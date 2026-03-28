#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""EarningsTracker fuer Airdrop Bot — verfolgt Quest-Abschluesse und Rewards."""
from __future__ import annotations
import json, logging
from datetime import datetime, timezone, date
UTC = timezone.utc
from pathlib import Path

log = logging.getLogger("Airdrop.Earnings")
EARNINGS_FILE = Path(__file__).parent.parent / "state" / "earnings.json"


class AirdropEarnings:
    def __init__(self):
        self._data = self._load()

    def record_quest(self, quest_id: str, quest_name: str, platform: str,
                     tasks_done: int, reward_type: str, est_eur: float = 0.0) -> None:
        entry = {
            "timestamp":  datetime.now(UTC).isoformat(),
            "date":       str(date.today()),
            "quest_id":   quest_id,
            "quest_name": quest_name,
            "platform":   platform,
            "tasks_done": tasks_done,
            "reward_type":reward_type,
            "est_eur":    est_eur,
        }
        self._data.setdefault("quests", []).append(entry)
        self._save()
        log.info(f"Quest abgeschlossen: {quest_name} ({platform}) +{est_eur:.2f} EUR gesch.")

    def format_report(self) -> str:
        today   = str(date.today())
        all_q   = self._data.get("quests", [])
        today_q = [q for q in all_q if q.get("date") == today]
        total_est  = sum(q.get("est_eur", 0) for q in all_q)
        today_est  = sum(q.get("est_eur", 0) for q in today_q)

        lines = [
            "",
            "=" * 55,
            f"  AIRDROP EARNINGS — {today}",
            "=" * 55,
            f"  Heute:  {len(today_q)} Quests | ~{today_est:.2f} EUR (geschaetzt)",
            f"  Gesamt: {len(all_q)} Quests  | ~{total_est:.2f} EUR (geschaetzt)",
            "",
        ]
        if today_q:
            lines.append("  Heute abgeschlossen:")
            for q in today_q[-5:]:
                lines.append(f"    - [{q['platform']}] {q['quest_name'][:40]}")
        lines.append("=" * 55)
        return "\n".join(lines)

    def _save(self) -> None:
        EARNINGS_FILE.parent.mkdir(exist_ok=True)
        EARNINGS_FILE.write_text(json.dumps(self._data, indent=2))

    def _load(self) -> dict:
        try:
            if EARNINGS_FILE.exists():
                return json.loads(EARNINGS_FILE.read_text())
        except Exception:
            pass
        return {"quests": []}
