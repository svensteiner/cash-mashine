#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FaucetScheduler — Verwaltet Claim-Zeiten und Warteschlange aller Faucets.

Weiss wann jeder Faucet wieder claimbar ist und sortiert die Queue.
"""
from __future__ import annotations
import json, logging, time
from datetime import datetime, UTC
from pathlib import Path

log = logging.getLogger("Faucet.Scheduler")
STATE_FILE = Path(__file__).parent.parent / "state" / "schedule.json"


class FaucetScheduler:
    def __init__(self):
        self._last_claim: dict[str, float] = {}   # faucet_id -> unix timestamp
        self._load()

    def record_claim(self, faucet_id: str) -> None:
        self._last_claim[faucet_id] = time.time()
        self._save()

    def is_ready(self, faucet: dict) -> bool:
        last = self._last_claim.get(faucet["id"], 0)
        cooldown = faucet.get("cooldown_minutes", 60) * 60
        return (time.time() - last) >= cooldown

    def next_claim_in(self, faucet: dict) -> int:
        """Sekunden bis naechster Claim moeglich."""
        last = self._last_claim.get(faucet["id"], 0)
        cooldown = faucet.get("cooldown_minutes", 60) * 60
        remaining = cooldown - (time.time() - last)
        return max(0, int(remaining))

    def get_ready_faucets(self, all_faucets: list[dict]) -> list[dict]:
        return [f for f in all_faucets if f.get("enabled") and self.is_ready(f)]

    def get_next_ready_at(self, all_faucets: list[dict]) -> float:
        """Unix-Timestamp wann der naechste Faucet ready ist."""
        times = []
        for f in all_faucets:
            if not f.get("enabled"):
                continue
            last = self._last_claim.get(f["id"], 0)
            cooldown = f.get("cooldown_minutes", 60) * 60
            ready_at = last + cooldown
            times.append(ready_at)
        return min(times) if times else time.time()

    def status_table(self, all_faucets: list[dict]) -> str:
        lines = [
            "",
            "=" * 60,
            "  FAUCET SCHEDULE",
            "  " + "-" * 56,
            f"  {'Faucet':<20} {'Status':<12} {'Naechster Claim'}",
            "  " + "-" * 56,
        ]
        for f in all_faucets:
            if not f.get("enabled"):
                lines.append(f"  {f['name']:<20} {'DEAKTIVIERT':<12}")
                continue
            if self.is_ready(f):
                status = "JETZT READY"
                next_t = "sofort"
            else:
                secs = self.next_claim_in(f)
                mins = secs // 60
                status = f"Wartet"
                next_t = f"in {mins} Min"
            lines.append(f"  {f['name']:<20} {status:<12} {next_t}")
        lines.append("=" * 60)
        return "\n".join(lines)

    def _save(self) -> None:
        STATE_FILE.parent.mkdir(exist_ok=True)
        STATE_FILE.write_text(json.dumps(self._last_claim, indent=2))

    def _load(self) -> None:
        try:
            if STATE_FILE.exists():
                self._last_claim = json.loads(STATE_FILE.read_text())
        except Exception:
            self._last_claim = {}
