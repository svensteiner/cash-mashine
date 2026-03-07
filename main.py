#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cash Mashine — Haupteinstiegspunkt.

Startet ein einzelnes Agenten-Rennen:
  1. Alle Agenten suchen parallel im Internet nach Geldverdien-Ideen
  2. Scorer bewertet alle Ideen
  3. Brain waehlt den Gewinner und erstellt Umsetzungsplan

Usage:
  python main.py              — Ein einzelnes Rennen
  python main.py --status     — Zeigt Control Center Status
  python main.py --history    — Zeigt Rennen-Historie
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Projekt-Root in sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# dotenv laden
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import openai
from core.race_engine import RaceEngine
from core.control_center import ControlCenter

# ------------------------------------------------------------------ #
# Logging Setup (aus MarketingBot-Pattern)                             #
# ------------------------------------------------------------------ #
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "cash_mashine.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("CashMashine")

# Silence noisy third-party loggers
for noisy in ["httpx", "openai", "httpcore"]:
    logging.getLogger(noisy).setLevel(logging.WARNING)


# ------------------------------------------------------------------ #
# Config laden                                                         #
# ------------------------------------------------------------------ #
def load_config() -> dict:
    config_file = ROOT / "config.json"
    defaults = {
        "model": "gpt-4o-mini",
        "model_brain": "gpt-4o",
        "race_interval_minutes": 60,
        "max_rounds": 0,  # 0 = unendlich (fuer dauerlauf.py)
    }
    if config_file.exists():
        try:
            loaded = json.loads(config_file.read_text())
            defaults.update(loaded)
        except Exception as e:
            log.warning(f"Config-Ladefehler: {e} — nutze Defaults")
    return defaults


def check_api_key() -> str:
    provider = os.environ.get("API_PROVIDER", "openrouter").lower()
    if provider == "openrouter":
        key = os.environ.get("OPENROUTER_API_KEY", "")
        if key:
            return key
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        print("\n[FEHLER] Kein API-Key gesetzt!")
        print("  .env: OPENROUTER_API_KEY=sk-or-v1-... oder OPENAI_API_KEY=sk-...")
        sys.exit(1)
    return key


def build_client(config: dict) -> openai.OpenAI:
    provider = os.environ.get("API_PROVIDER", "openrouter").lower()
    key = check_api_key()
    if provider == "openrouter":
        return openai.OpenAI(
            api_key=key,
            base_url="https://openrouter.ai/api/v1",
        )
    return openai.OpenAI(api_key=key)


# ------------------------------------------------------------------ #
# CLI                                                                  #
# ------------------------------------------------------------------ #
def show_status() -> None:
    state_dir = ROOT / "state"
    cc = ControlCenter(state_dir)
    cc.print_dashboard(state_dir / "race_results.json")

    ideas_file = state_dir / "ideas.json"
    if ideas_file.exists():
        ideas = json.loads(ideas_file.read_text())
        print(f"  Gespeicherte Ideen: {len(ideas)}")
        print(f"  Top-Idee: {ideas[0]['title'] if ideas else 'keine'}\n")


def show_history() -> None:
    results_file = ROOT / "state" / "race_results.json"
    if not results_file.exists():
        print("Noch keine Rennen gelaufen.")
        return
    data = json.loads(results_file.read_text())
    print(f"\n=== RENNEN-HISTORIE ({data.get('total_races', 0)} Rennen) ===")
    for race in data.get("history", [])[-5:]:
        winner = race.get("winner", {})
        ts = race.get("timestamp", "")[:16]
        print(f"  [{ts}] Rennen #{race.get('race_number', '?')}: "
              f"{winner.get('title', '?')[:40]} "
              f"(Score: {winner.get('raw_score', 0):.3f})")
    print()


# ------------------------------------------------------------------ #
# Main                                                                 #
# ------------------------------------------------------------------ #
async def main() -> None:
    args = sys.argv[1:]

    if "--status" in args:
        show_status()
        return
    if "--history" in args:
        show_history()
        return

    print()
    print("=" * 65)
    print("  CASH MASHINE v1.0 -- AGENTEN-RENNEN")
    print("  Mehrere KI-Agenten suchen parallel nach Geld-Ideen")
    print("=" * 65)
    print()

    config = load_config()
    client = build_client(config)

    engine = RaceEngine(client, config)
    decision = await engine.run_race()

    if decision:
        log.info("Rennen abgeschlossen. Gewinner gespeichert in state/brain_state.json")
    else:
        log.warning("Rennen ohne Gewinner beendet.")


if __name__ == "__main__":
    asyncio.run(main())
