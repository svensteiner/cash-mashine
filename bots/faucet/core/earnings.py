#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""EarningsTracker — Verfolgt alle Faucet-Gewinne und erstellt Berichte."""
from __future__ import annotations
import json, logging
from datetime import datetime, UTC, date
from pathlib import Path

log = logging.getLogger("Faucet.Earnings")
EARNINGS_FILE = Path(__file__).parent.parent / "state" / "earnings.json"


class EarningsTracker:
    def __init__(self):
        self._data: dict = self._load()

    def record(self, faucet_id: str, faucet_name: str, crypto: str,
               amount: float, amount_usd: float) -> None:
        entry = {
            "timestamp":   datetime.now(UTC).isoformat(),
            "date":        str(date.today()),
            "faucet_id":   faucet_id,
            "faucet_name": faucet_name,
            "crypto":      crypto,
            "amount":      amount,
            "amount_usd":  amount_usd,
        }
        self._data.setdefault("claims", []).append(entry)
        self._save()
        log.info(f"Earnings: +{amount} {crypto} (~${amount_usd:.4f}) von {faucet_name}")

    def record_skip(self, faucet_id: str, reason: str) -> None:
        log.debug(f"Skip {faucet_id}: {reason}")

    def daily_summary(self) -> dict:
        today = str(date.today())
        claims = [c for c in self._data.get("claims", []) if c.get("date") == today]
        total_usd = sum(c.get("amount_usd", 0) for c in claims)
        by_crypto: dict[str, float] = {}
        for c in claims:
            by_crypto[c["crypto"]] = by_crypto.get(c["crypto"], 0) + c.get("amount", 0)
        return {
            "date":        today,
            "claims":      len(claims),
            "total_usd":   round(total_usd, 6),
            "total_eur":   round(total_usd * 0.92, 6),  # grober EUR-Umrechnungsfaktor
            "by_crypto":   by_crypto,
        }

    def total_summary(self) -> dict:
        claims = self._data.get("claims", [])
        total_usd = sum(c.get("amount_usd", 0) for c in claims)
        days = len({c.get("date") for c in claims})
        return {
            "total_claims": len(claims),
            "total_usd":    round(total_usd, 6),
            "total_eur":    round(total_usd * 0.92, 6),
            "active_days":  days,
            "avg_usd_day":  round(total_usd / days, 6) if days > 0 else 0,
        }

    def format_report(self) -> str:
        daily  = self.daily_summary()
        total  = self.total_summary()
        lines  = [
            "",
            "=" * 55,
            f"  FAUCET EARNINGS — {daily['date']}",
            "=" * 55,
            f"  Heute:  {daily['claims']} Claims | ${daily['total_usd']:.5f} (~{daily['total_eur']:.5f} EUR)",
        ]
        if daily["by_crypto"]:
            for crypto, amt in daily["by_crypto"].items():
                lines.append(f"    {crypto}: {amt:.8f}")
        lines += [
            "",
            f"  Gesamt: {total['total_claims']} Claims | ${total['total_usd']:.4f} (~{total['total_eur']:.4f} EUR)",
            f"  Aktive Tage:  {total['active_days']}",
            f"  Schnitt/Tag:  ${total['avg_usd_day']:.5f}",
            "=" * 55,
        ]
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
        return {"claims": []}
