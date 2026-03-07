#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DeFi Yield Bot — Haupteinstiegspunkt.

Ueberwacht deine Stablecoin-Position, findet beste Yields,
berechnet Compound-Timing und erstellt taeglich einen Bericht.

Usage:
  python main.py              — Einmal ausfuehren + Bericht
  python main.py --yields     — Nur aktuelle Yield-Tabelle
  python main.py --status     — Nur deine Position
  python main.py --history    — Earnings-Historie
"""
from __future__ import annotations
import json, logging, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent.parent.parent))  # Cash Mashine Root

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from core.yield_scanner   import YieldScanner
from core.position_monitor import PositionMonitor
from core.report          import ReportGenerator
from core.alerts          import AlertSystem

# ------------------------------------------------------------------ #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(ROOT / "state" / "defi_bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("DeFiBot")
for n in ["httpx", "urllib3"]:
    logging.getLogger(n).setLevel(logging.WARNING)
# ------------------------------------------------------------------ #


def load_config() -> dict:
    return {
        "wallet_address":      os.environ.get("WALLET_ADDRESS", ""),
        "target_chain":        os.environ.get("TARGET_CHAIN", "Arbitrum"),
        "target_protocol":     os.environ.get("TARGET_PROTOCOL", "aave-v3"),
        "capital_eur":         float(os.environ.get("CAPITAL_EUR", 5000)),
        "min_apy_threshold":   float(os.environ.get("MIN_APY_THRESHOLD", 3.0)),
        "min_tvl_usd":         50_000_000,
        "only_stablecoins":    True,
        "safe_protocols_only": True,
    }


def run(config: dict) -> None:
    scanner  = YieldScanner(config)
    monitor  = PositionMonitor(config)
    reporter = ReportGenerator()
    alerts   = AlertSystem(config)

    chain    = config["target_chain"]
    protocol = config["target_protocol"]
    capital  = config["capital_eur"]

    # 1) Yields scannen
    print("\n  [1/4] Scanne aktuelle DeFi-Yields...")
    all_pools = scanner.get_best_pools(chains=[chain, "Ethereum", "Arbitrum", "Base"])
    print(scanner.summary_table(all_pools, top_n=8))
    print(scanner.earnings_preview(capital, all_pools, top_n=5))

    # Besten Pool fuer Ziel-Protokoll finden
    target_pool = next(
        (p for p in all_pools if p["project"] == protocol), None
    ) or (all_pools[0] if all_pools else None)

    if not target_pool:
        log.error("Kein passender Pool gefunden.")
        return

    current_apy = target_pool["apy"]
    best_apy    = all_pools[0]["apy"] if all_pools else current_apy

    # 2) Position pruefen
    print(f"\n  [2/4] Pruefe Wallet-Position ({chain})...")
    if monitor.is_configured():
        snap     = monitor.get_snapshot()
        earnings = monitor.get_earnings_estimate(current_apy)
        print(monitor.format_snapshot(snap, earnings))
    else:
        print("  Wallet-Adresse nicht konfiguriert — nur Markt-Analyse.")
        earnings = monitor.get_earnings_estimate(current_apy)
        print(f"\n  Rendite-Schaetzung bei {current_apy:.1f}% APY:")
        print(f"    {capital:,.0f} EUR -> {earnings['daily_eur']:.4f} EUR/Tag")
        print(f"    {capital:,.0f} EUR -> {earnings['monthly_eur']:.2f} EUR/Monat")
        print(f"    {capital:,.0f} EUR -> {earnings['yearly_eur']:.2f} EUR/Jahr")
        snap = {}

    # 3) Compound-Empfehlung (typischer Arbitrum Gas: ~0.50 USD)
    print(f"\n  [3/4] Compound-Analyse...")
    gas_usd      = 0.50 if chain == "Arbitrum" else 5.0
    compound_rec = monitor.compound_recommendation(current_apy, gas_usd)
    print(f"  Gas-Kosten:  ~${gas_usd:.2f} ({chain})")
    print(f"  Empfehlung:  {compound_rec['recommendation']}")

    # 4) Alerts + Report
    print(f"\n  [4/4] Alerts pruefen + Bericht erstellen...")
    alert_msgs = alerts.check_and_alert(current_apy, best_apy, capital)
    for msg in alert_msgs:
        print(f"  [!] {msg}")

    report = reporter.daily_report(all_pools, earnings, snap, compound_rec)
    print(report)

    # Earning-Summary
    print(reporter.total_earnings_summary())


def show_history() -> None:
    from core.report import ReportGenerator
    rg = ReportGenerator()
    print(rg.total_earnings_summary())
    # Liste gespeicherter Reports
    reports = sorted((ROOT / "reports").glob("report_*.txt"), reverse=True)
    print(f"\n  Gespeicherte Berichte: {len(reports)}")
    for r in reports[:5]:
        print(f"    - {r.name}")


def show_yields_only() -> None:
    config  = load_config()
    scanner = YieldScanner(config)
    pools   = scanner.get_best_pools()
    print(scanner.summary_table(pools, top_n=15))
    print(scanner.earnings_preview(config["capital_eur"], pools, top_n=8))


# ------------------------------------------------------------------ #
if __name__ == "__main__":
    args = sys.argv[1:]
    (ROOT / "state").mkdir(exist_ok=True)

    if "--yields" in args:
        show_yields_only()
    elif "--history" in args:
        show_history()
    else:
        run(load_config())
