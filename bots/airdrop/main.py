#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Airdrop Quest Bot — Haupteinstiegspunkt.

Findet automatable Quests auf Galxe und Layer3,
fuehrt Twitter/Discord-Tasks automatisch aus,
loest Quizze per LLM und trackt Earnings.

Usage:
  python main.py              — Quests scannen + ausfuehren
  python main.py --scan       — Nur scannen, nicht ausfuehren
  python main.py --status     — Earnings-Report
  python main.py --galxe      — Nur Galxe-Quests anzeigen
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

import openai
from platforms.galxe   import GalxeClient
from platforms.layer3  import Layer3Client
from core.task_executor import TaskExecutor
from core.earnings      import AirdropEarnings

# ------------------------------------------------------------------ #
(ROOT / "state").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(ROOT / "state" / "airdrop_bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("AirdropBot")
for n in ["httpx", "urllib3"]:
    logging.getLogger(n).setLevel(logging.WARNING)
# ------------------------------------------------------------------ #

COMPLETED_FILE = ROOT / "state" / "completed_quests.json"


def load_config() -> dict:
    return {
        "model":        os.environ.get("MODEL", "openai/gpt-4o-mini"),
        "browser_mode": os.environ.get("BROWSER_MODE", "persistent"),
        "cdp_port":     int(os.environ.get("CDP_PORT", 9225)),
        "max_quests_per_run": int(os.environ.get("MAX_QUESTS", 5)),
        "only_automatable":   os.environ.get("ONLY_AUTO", "true").lower() == "true",
    }


def build_llm(config: dict):
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if key:
        return openai.OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
    key = os.environ.get("OPENAI_API_KEY", "")
    return openai.OpenAI(api_key=key) if key else None


def load_completed() -> set:
    try:
        if COMPLETED_FILE.exists():
            return set(json.loads(COMPLETED_FILE.read_text()))
    except Exception:
        pass
    return set()


def save_completed(completed: set) -> None:
    COMPLETED_FILE.write_text(json.dumps(list(completed)))


def scan_quests(config: dict) -> tuple[list, list]:
    """Scannt alle Plattformen nach Quests."""
    print("\n  [1] Scanne Galxe...")
    galxe  = GalxeClient()
    g_quests = galxe.get_active_quests(limit=20)
    print(f"  Galxe: {len(g_quests)} aktive Quests gefunden "
          f"({sum(1 for q in g_quests if q.automatable)} automatisierbar)")

    print("\n  [2] Scanne Layer3...")
    layer3   = Layer3Client()
    l_quests = layer3.get_active_quests(limit=10)
    print(f"  Layer3: {len(l_quests)} Quests gefunden")

    return g_quests, l_quests


def execute_quests(g_quests: list, config: dict, llm) -> None:
    """Fuehrt automatable Galxe-Quests aus."""
    completed = load_completed()
    earnings  = AirdropEarnings()
    executor  = TaskExecutor(config, llm)
    max_q     = config.get("max_quests_per_run", 5)

    # Nur automatable, noch nicht abgeschlossene Quests
    to_do = [
        q for q in g_quests
        if q.automatable and q.id not in completed
    ][:max_q]

    if not to_do:
        print("\n  Keine neuen automatisierbaren Quests verfuegbar.")
        print(f"  (Bereits abgeschlossen: {len(completed)} Quests)")
        return

    print(f"\n  [3] Fuehre {len(to_do)} Quests aus — starte Browser...")
    if not executor.start_browser():
        log.error("Browser-Start fehlgeschlagen.")
        return

    try:
        for quest in to_do:
            print(f"\n  --> QUEST: {quest.name[:55]}")
            print(f"      URL:   {quest.url}")
            print(f"      Tasks: {len(quest.tasks)}")

            # Galxe Quest-Seite oeffnen
            executor._page.goto(quest.url, wait_until="domcontentloaded", timeout=25000)
            time.sleep(3)

            success_count = 0
            for task in quest.tasks:
                result = executor.execute(task)
                icon   = "[OK]" if result.success else ("[--]" if result.skipped else "[!!]")
                print(f"      {icon} {task['type']}: {result.message[:50]}")
                if result.success:
                    success_count += 1
                time.sleep(2)

            # Als abgeschlossen markieren (auch bei Teilabschluss)
            completed.add(quest.id)
            save_completed(completed)
            earnings.record_quest(
                quest_id    = quest.id,
                quest_name  = quest.name,
                platform    = "galxe",
                tasks_done  = success_count,
                reward_type = quest.reward_type,
                est_eur     = quest.estimated_eur if success_count == len(quest.tasks) else 0.5,
            )
            print(f"      Abgeschlossen: {success_count}/{len(quest.tasks)} Tasks")
            time.sleep(5)

    finally:
        executor.stop_browser()

    print(earnings.format_report())


def show_galxe_only() -> None:
    galxe  = GalxeClient()
    quests = galxe.get_active_quests(limit=20)
    print(galxe.format_quest_list(quests, top_n=15))


# ------------------------------------------------------------------ #
if __name__ == "__main__":
    args   = sys.argv[1:]
    config = load_config()
    llm    = build_llm(config)

    print()
    print("=" * 60)
    print("  AIRDROP QUEST BOT")
    print("  Galxe + Layer3 | Twitter + Discord + Quiz")
    print("=" * 60)

    if "--status" in args:
        print(AirdropEarnings().format_report())
    elif "--galxe" in args:
        show_galxe_only()
    elif "--scan" in args:
        g, l = scan_quests(config)
        galxe = GalxeClient()
        print(galxe.format_quest_list(g, top_n=15))
    else:
        g, l = scan_quests(config)
        galxe = GalxeClient()
        print(galxe.format_quest_list(g, top_n=8))
        execute_quests(g, config, llm)
