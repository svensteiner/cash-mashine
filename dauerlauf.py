#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
dauerlauf.py — Kontinuierlicher Betrieb der Cash Mashine.

Laeuft in einer Endlosschleife und startet Rennen in konfigurierten Intervallen.
Zwischen den Rennen schlaeft er — wacht auf und startet das naechste Rennen.

Pattern aus MarketingBot-dauerlauf.py uebernommen.

Usage:
  python dauerlauf.py                  — Startet Dauerlauf
  python dauerlauf.py --rounds 3       — Nur 3 Rennen laufen
  python dauerlauf.py --interval 30    — Alle 30 Minuten ein Rennen
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import openai
from core.race_engine import RaceEngine
from core.control_center import ControlCenter

# ------------------------------------------------------------------ #
# Logging                                                              #
# ------------------------------------------------------------------ #
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOCK_FILE = ROOT / "dauerlauf.lock"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "dauerlauf.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("CashMashine.Dauerlauf")
for noisy in ["httpx", "openai", "httpcore"]:
    logging.getLogger(noisy).setLevel(logging.WARNING)


# ------------------------------------------------------------------ #
# Shutdown Handler                                                     #
# ------------------------------------------------------------------ #
_running = True

def _handle_signal(sig, frame):
    global _running
    log.info(f"Signal {sig} empfangen — stoppe nach aktuellem Rennen...")
    _running = False

signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ------------------------------------------------------------------ #
# Config + Lock                                                        #
# ------------------------------------------------------------------ #
def load_config() -> dict:
    defaults = {
        "model": "gpt-4o-mini",
        "model_brain": "gpt-4o",
        "race_interval_minutes": 60,
    }
    config_file = ROOT / "config.json"
    if config_file.exists():
        try:
            defaults.update(json.loads(config_file.read_text()))
        except Exception:
            pass
    return defaults


def acquire_lock() -> bool:
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            # Pruefe ob Prozess noch laeuft
            import subprocess
            result = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
            if str(pid) in result.stdout:
                log.error(f"Dauerlauf laeuft bereits (PID {pid}). Lock: {LOCK_FILE}")
                return False
        except Exception:
            pass  # Lock-File veraltet — ueberschreiben
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def release_lock() -> None:
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


# ------------------------------------------------------------------ #
# Main Dauerlauf                                                       #
# ------------------------------------------------------------------ #
async def dauerlauf(max_rounds: int = 0, interval_minutes: int = 0) -> None:
    global _running

    config = load_config()
    if interval_minutes > 0:
        config["race_interval_minutes"] = interval_minutes

    interval_secs = config["race_interval_minutes"] * 60

    # API Client (OpenRouter bevorzugt, Fallback OpenAI)
    provider = os.environ.get("API_PROVIDER", "openrouter").lower()
    if provider == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if api_key:
            client = openai.OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        else:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            client = openai.OpenAI(api_key=api_key)
    else:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        client = openai.OpenAI(api_key=api_key)

    if not api_key:
        log.error("Kein API-Key gesetzt! .env anlegen.")
        sys.exit(1)
    engine = RaceEngine(client, config)
    cc = ControlCenter(ROOT / "state")

    round_num = 0
    log.info(f"Cash Mashine DAUERLAUF gestartet | Intervall: {config['race_interval_minutes']} Min")
    inf_str = "unbegrenzt" if max_rounds == 0 else str(max_rounds)
    print()
    print("=" * 65)
    print("  CASH MASHINE -- DAUERLAUF GESTARTET")
    print(f"  Intervall: {config['race_interval_minutes']} Min | Max-Runden: {inf_str}")
    print("  Stopp: Ctrl+C")
    print("=" * 65)
    print()

    while _running:
        round_num += 1
        if max_rounds > 0 and round_num > max_rounds:
            log.info(f"Max-Runden ({max_rounds}) erreicht — stoppe Dauerlauf.")
            break

        log.info(f"--- RUNDE {round_num} START ---")
        try:
            decision = await engine.run_race()
            if decision:
                winner = decision.get("winner", {})
                log.info(f"Runde {round_num} Gewinner: {winner.get('title', '?')} "
                         f"(Score: {winner.get('raw_score', 0):.3f})")
        except Exception as e:
            log.error(f"Runde {round_num} Fehler: {e}", exc_info=True)

        if not _running:
            break

        if max_rounds > 0 and round_num >= max_rounds:
            break

        # Auf naechstes Rennen warten
        next_time = datetime.now()
        log.info(f"Naechstes Rennen in {config['race_interval_minutes']} Min "
                 f"(~{next_time.strftime('%H:%M')})")
        print(f"\n  [PAUSE] Warte {config['race_interval_minutes']} Minuten bis zum naechsten Rennen...")
        print(f"  Stopp: Ctrl+C\n")

        # Warte in kleinen Schritten (damit Ctrl+C schnell reagiert)
        wait_start = time.time()
        while _running and (time.time() - wait_start) < interval_secs:
            await asyncio.sleep(5)

    log.info("Cash Mashine Dauerlauf beendet.")
    cc.print_dashboard(ROOT / "state" / "race_results.json")


def parse_args() -> tuple[int, int]:
    args = sys.argv[1:]
    rounds = 0
    interval = 0
    for i, arg in enumerate(args):
        if arg == "--rounds" and i + 1 < len(args):
            try:
                rounds = int(args[i + 1])
            except ValueError:
                pass
        if arg == "--interval" and i + 1 < len(args):
            try:
                interval = int(args[i + 1])
            except ValueError:
                pass
    return rounds, interval


if __name__ == "__main__":
    if not acquire_lock():
        sys.exit(1)
    try:
        rounds, interval = parse_args()
        asyncio.run(dauerlauf(max_rounds=rounds, interval_minutes=interval))
    finally:
        release_lock()
