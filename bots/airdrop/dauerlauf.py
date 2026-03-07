#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dauerlauf.py — Scannt und claimt Quests alle 2 Stunden."""
from __future__ import annotations
import logging, os, signal, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
except ImportError: pass

from main import load_config, build_llm, scan_quests, execute_quests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(ROOT / "state" / "dauerlauf.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("AirdropBot.Dauerlauf")

_running = True
LOCK = ROOT / "dauerlauf.lock"

def _stop(sig, frame):
    global _running
    _running = False
    log.info("Stopp...")

signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)

INTERVAL_H = 2  # Alle 2 Stunden neue Quests suchen

if __name__ == "__main__":
    if LOCK.exists():
        log.error("Dauerlauf laeuft bereits.")
        sys.exit(1)
    LOCK.write_text(str(os.getpid()))

    print()
    print("=" * 60)
    print("  AIRDROP BOT -- DAUERLAUF")
    print(f"  Quest-Scan alle {INTERVAL_H} Stunden | Ctrl+C zum Stoppen")
    print("=" * 60)
    print()

    config  = load_config()
    llm     = build_llm(config)
    round_n = 0

    try:
        while _running:
            round_n += 1
            log.info(f"--- Runde {round_n} ---")
            try:
                g, l = scan_quests(config)
                execute_quests(g, config, llm)
            except Exception as e:
                log.error(f"Runde {round_n}: {e}", exc_info=True)

            if not _running:
                break

            wait_s = INTERVAL_H * 3600
            log.info(f"Naechster Scan in {INTERVAL_H}h | Ctrl+C zum Stoppen")
            waited = 0
            while _running and waited < wait_s:
                time.sleep(30)
                waited += 30
    finally:
        LOCK.unlink(missing_ok=True)
        log.info("Airdrop Bot Dauerlauf beendet.")
