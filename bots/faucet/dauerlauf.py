#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
dauerlauf.py — Laeuft kontinuierlich, claimt sobald Faucets ready sind.

Prueft alle 5 Minuten ob ein Faucet claimbar ist.
Schlaeft effizient bis zum naechsten Claim-Zeitpunkt.
"""
from __future__ import annotations
import json, logging, os, signal, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
except ImportError: pass

from main import load_faucets, load_config, run_claims
from core.schedule import FaucetScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(ROOT / "state" / "dauerlauf.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("FaucetBot.Dauerlauf")

_running = True
LOCK = ROOT / "dauerlauf.lock"

def _stop(sig, frame):
    global _running
    log.info("Stopp-Signal empfangen...")
    _running = False

signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)


if __name__ == "__main__":
    if LOCK.exists():
        log.error("Dauerlauf laeuft bereits.")
        sys.exit(1)
    LOCK.write_text(str(os.getpid()))

    print()
    print("=" * 55)
    print("  FAUCET BOT -- DAUERLAUF")
    print("  Claimt automatisch wenn Faucets ready sind")
    print("  Stopp: Ctrl+C")
    print("=" * 55)
    print()

    faucets, wallets = load_faucets()
    config    = load_config()
    scheduler = FaucetScheduler()
    round_n   = 0

    try:
        while _running:
            ready = scheduler.get_ready_faucets(faucets)
            if ready:
                round_n += 1
                log.info(f"--- Runde {round_n}: {len(ready)} Faucets ready ---")
                try:
                    run_claims(faucets, wallets, config)
                except Exception as e:
                    log.error(f"Claim-Fehler: {e}", exc_info=True)
            else:
                # Bis zum naechsten Faucet schlafen
                next_ts  = scheduler.get_next_ready_at(faucets)
                wait_s   = max(60, int(next_ts - time.time()))
                wait_m   = wait_s // 60
                log.info(f"Alle Faucets geclaimed. Naechster in {wait_m} Min.")
                print(f"  [PAUSE] Naechster Claim in {wait_m} Minuten | Ctrl+C zum Stoppen")
                # In 60s-Schritten warten (schnelle Reaktion auf Ctrl+C)
                waited = 0
                while _running and waited < wait_s:
                    time.sleep(min(60, wait_s - waited))
                    waited += 60
    finally:
        LOCK.unlink(missing_ok=True)
        log.info("Faucet Bot Dauerlauf beendet.")
