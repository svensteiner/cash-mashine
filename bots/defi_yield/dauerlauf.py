#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dauerlauf.py — Laeufst den DeFi Yield Bot sttaendig (alle 6h default)."""
from __future__ import annotations
import asyncio, json, logging, os, signal, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
except ImportError: pass

from main import load_config, run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(ROOT / "state" / "dauerlauf.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("DeFiBot.Dauerlauf")

_running = True
LOCK = ROOT / "dauerlauf.lock"

def _stop(sig, frame):
    global _running
    log.info(f"Signal {sig} — stoppe...")
    _running = False

signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)


if __name__ == "__main__":
    interval_h = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    interval_s = interval_h * 3600

    if LOCK.exists():
        log.error("Dauerlauf laeuft bereits (Lock-File vorhanden).")
        sys.exit(1)
    LOCK.write_text(str(os.getpid()))

    print()
    print("=" * 60)
    print("  DEFI YIELD BOT -- DAUERLAUF")
    print(f"  Analyse alle {interval_h} Stunden | Ctrl+C zum Stoppen")
    print("=" * 60)
    print()

    cfg = load_config()
    round_n = 0
    try:
        while _running:
            round_n += 1
            log.info(f"--- Runde {round_n} Start ---")
            try:
                run(cfg)
            except Exception as e:
                log.error(f"Runde {round_n} Fehler: {e}", exc_info=True)

            if not _running: break
            log.info(f"Naechste Analyse in {interval_h}h | Ctrl+C zum Stoppen")
            wait_start = time.time()
            while _running and (time.time() - wait_start) < interval_s:
                time.sleep(10)
    finally:
        LOCK.unlink(missing_ok=True)
        log.info("DeFi Yield Bot Dauerlauf beendet.")
