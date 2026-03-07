#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Faucet Bot — Haupteinstiegspunkt.

Claimt automatisch von mehreren Krypto-Faucets.
Wartet auf Cooldowns und startet erneut.

Usage:
  python main.py              — Einmalig alle ready Faucets claimen
  python main.py --status     — Schedule + Earnings anzeigen
  python main.py --earnings   — Nur Earnings-Report
  python main.py --list       — Alle Faucets auflisten
"""
from __future__ import annotations
import json, logging, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from core.schedule import FaucetScheduler
from core.earnings import EarningsTracker
from core.claimer  import FaucetClaimer

# ------------------------------------------------------------------ #
(ROOT / "state").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(ROOT / "state" / "faucet_bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("FaucetBot")
for n in ["urllib3", "httpx"]:
    logging.getLogger(n).setLevel(logging.WARNING)
# ------------------------------------------------------------------ #


def load_faucets() -> tuple[list, dict]:
    cfg   = json.loads((ROOT / "faucets.json").read_text())
    return cfg["faucets"], cfg["wallet_addresses"]


def load_config() -> dict:
    return {
        "browser_mode": os.environ.get("BROWSER_MODE", "persistent"),
        "cdp_port":     int(os.environ.get("CDP_PORT", 9224)),
        "captcha_wait": int(os.environ.get("CAPTCHA_WAIT_SECS", 30)),
    }


def run_claims(faucets: list, wallets: dict, config: dict) -> None:
    scheduler = FaucetScheduler()
    earnings  = EarningsTracker()
    claimer   = FaucetClaimer(config, wallets)

    ready = scheduler.get_ready_faucets(faucets)
    print(f"\n  Ready zum Claimen: {len(ready)} von {sum(1 for f in faucets if f['enabled'])} aktiven Faucets")

    if not ready:
        next_ts = scheduler.get_next_ready_at(faucets)
        wait_m  = max(0, int((next_ts - time.time()) / 60))
        print(f"  Naechster Faucet ready in: {wait_m} Minuten")
        print(scheduler.status_table(faucets))
        return

    print("  Starte Browser...")
    if not claimer.start():
        log.error("Browser konnte nicht gestartet werden.")
        return

    try:
        claimed = 0
        for faucet in ready:
            print(f"\n  --> Claiming: {faucet['name']} ({faucet['crypto']})")
            result = claimer.claim(faucet)

            if result.success:
                scheduler.record_claim(faucet["id"])
                earnings.record(
                    faucet["id"], faucet["name"],
                    result.crypto or faucet["crypto"],
                    result.amount, result.amount_usd,
                )
                claimed += 1
                print(f"  [OK] +{result.amount} {result.crypto} (~${result.amount_usd:.5f})")
            else:
                print(f"  [!!] Fehlgeschlagen: {result.message}")
                # Trotzdem als "geclaimed" markieren um Spam zu vermeiden
                scheduler.record_claim(faucet["id"])

            time.sleep(3)

        print(f"\n  Erledigt: {claimed}/{len(ready)} erfolgreich geclaimt")
        print(earnings.format_report())

    finally:
        claimer.stop()


def show_status(faucets: list) -> None:
    scheduler = FaucetScheduler()
    earnings  = EarningsTracker()
    print(scheduler.status_table(faucets))
    print(earnings.format_report())


def show_earnings() -> None:
    earnings = EarningsTracker()
    print(earnings.format_report())


def list_faucets(faucets: list) -> None:
    print("\n  KONFIGURIERTE FAUCETS:")
    print("  " + "-" * 55)
    for f in faucets:
        status = "aktiv" if f.get("enabled") else "deaktiviert"
        print(f"  [{status:>12}] {f['name']:<20} {f['crypto']:<6} alle {f['cooldown_minutes']} Min")
        print(f"                  {f.get('notes', '')}")
    print()


# ------------------------------------------------------------------ #
if __name__ == "__main__":
    args    = sys.argv[1:]
    faucets, wallets = load_faucets()
    config  = load_config()

    print()
    print("=" * 55)
    print("  FAUCET BOT — Automatischer Krypto-Claimer")
    print("=" * 55)

    if "--status" in args:
        show_status(faucets)
    elif "--earnings" in args:
        show_earnings()
    elif "--list" in args:
        list_faucets(faucets)
    else:
        run_claims(faucets, wallets, config)
