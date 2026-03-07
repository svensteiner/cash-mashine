#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ReportGenerator — Erstellt taeglich einen Earnings-Report und speichert ihn.
"""
from __future__ import annotations
import json, logging
from datetime import datetime, UTC
from pathlib import Path

log = logging.getLogger("DeFi.Report")

REPORTS_DIR = Path(__file__).parent.parent / "reports"
EARNINGS_FILE = Path(__file__).parent.parent / "state" / "earnings.json"


class ReportGenerator:
    def __init__(self):
        REPORTS_DIR.mkdir(exist_ok=True)

    def daily_report(self, pools: list, earnings: dict, snap: dict, compound_rec: dict) -> str:
        today = datetime.now().strftime("%d.%m.%Y")
        best  = pools[0] if pools else {}

        lines = [
            "",
            "#" * 65,
            f"  DEFI YIELD BOT — TAGESBERICHT {today}",
            "#" * 65,
            "",
            "  MARKT-UEBERSICHT (Top 5 sichere Stablecoin-Yields):",
            "  " + "-" * 55,
        ]
        for p in pools[:5]:
            daily_5k = 5000 * p["apy"] / 100 / 365
            lines.append(
                f"  {p['project']:<18} {p['symbol']:<14} "
                f"{p['apy']:.1f}% APY  -> {daily_5k:.3f} EUR/Tag"
            )

        lines += [
            "",
            f"  DEINE POSITION:",
            "  " + "-" * 55,
            f"  Kapital:          {earnings['capital_eur']:,.0f} EUR",
            f"  Aktiver APY:      {earnings['apy_pct']:.2f}%",
            f"  Verdient heute:   {earnings['daily_eur']:.4f} EUR",
            f"  Verdient diese Woche:  {earnings['weekly_eur']:.3f} EUR",
            f"  Verdient diesen Monat: {earnings['monthly_eur']:.2f} EUR",
            f"  Hochrechnung Jahr:     {earnings['yearly_eur']:.2f} EUR",
            "",
            f"  COMPOUND-EMPFEHLUNG:",
            "  " + "-" * 55,
            f"  {compound_rec.get('recommendation', 'Keine Daten')}",
            "",
            "#" * 65,
        ]
        report_text = "\n".join(lines)
        self._save_report(report_text, today)
        self._save_earnings(earnings)
        return report_text

    def _save_report(self, text: str, date_str: str) -> None:
        fname = REPORTS_DIR / f"report_{date_str.replace('.', '-')}.txt"
        fname.write_text(text, encoding="utf-8")
        log.info(f"Bericht gespeichert: {fname.name}")

    def _save_earnings(self, earnings: dict) -> None:
        try:
            history = []
            if EARNINGS_FILE.exists():
                history = json.loads(EARNINGS_FILE.read_text()).get("history", [])
            entry = {**earnings, "date": datetime.now(UTC).isoformat()}
            history.append(entry)
            history = history[-90:]  # 90 Tage behalten
            EARNINGS_FILE.parent.mkdir(exist_ok=True)
            EARNINGS_FILE.write_text(json.dumps({"history": history}, indent=2))
        except Exception as e:
            log.error(f"Earnings speichern: {e}")

    def total_earnings_summary(self) -> str:
        if not EARNINGS_FILE.exists():
            return "  Noch keine Earnings-Daten vorhanden."
        try:
            history = json.loads(EARNINGS_FILE.read_text()).get("history", [])
            if not history:
                return "  Noch keine Daten."
            total = sum(e.get("daily_eur", 0) for e in history)
            days  = len(history)
            avg   = total / days if days > 0 else 0
            return (
                f"  Gesamteinnahmen ({days} Tage): {total:.4f} EUR\n"
                f"  Durchschnitt pro Tag: {avg:.4f} EUR"
            )
        except Exception:
            return "  Fehler beim Lesen der Earnings."
