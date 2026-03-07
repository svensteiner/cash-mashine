#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Galxe Platform Client — GraphQL API fuer aktive Kampagnen.

Galxe (ehemals Project Galaxy) ist die groesste Quest-Plattform.
API: https://graphigo.prd.galaxy.eco/query
"""
from __future__ import annotations
import json, logging, time
from dataclasses import dataclass, field
from pathlib import Path
import requests

log = logging.getLogger("Airdrop.Galxe")

GRAPHQL_URL = "https://graphigo.prd.galaxy.eco/query"
CACHE_FILE  = Path(__file__).parent.parent / "state" / "galxe_cache.json"
CACHE_TTL   = 600  # 10 Minuten

# Task-Typen die wir automatisieren koennen (Galxe-echte Typen)
AUTOMATABLE_CRED_TYPES = {
    # Twitter (Galxe fasst alle Twitter-Tasks unter "TWITTER" zusammen)
    "TWITTER", "TWITTER_FOLLOW", "TWITTER_RETWEET", "TWITTER_LIKE", "TWITTER_TWEET",
    # Discord
    "DISCORD",
    # Links besuchen
    "GALXE_ID", "VISIT_LINK",
    # Quiz
    "QUIZ", "GALXE_QUIZ",
}

# Typen die wir NICHT automatisieren koennen (On-Chain, Email, etc.)
NON_AUTOMATABLE_CRED_TYPES = {
    "EVM_ADDRESS", "SOLANA_ADDRESS", "KADENA_ADDRESS", "APTOS_ADDRESS",
    "EMAIL", "PHONE", "KYC", "SNAPSHOT",
}


@dataclass
class GalxeQuest:
    id: str
    name: str
    url: str
    reward_type: str
    reward_name: str = ""
    tasks: list[dict] = field(default_factory=list)
    automatable: bool = False
    difficulty_score: float = 1.0   # 1.0 = leicht, 0.0 = schwer/manuell
    estimated_eur: float = 0.0


class GalxeClient:
    def __init__(self):
        self._cache: dict = {}

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def get_active_quests(self, limit: int = 20) -> list[GalxeQuest]:
        """Gibt automatable aktive Galxe-Quests zurueck."""
        raw = self._fetch_campaigns(limit)
        quests = []
        for camp in raw:
            quest = self._parse_campaign(camp)
            if quest:
                quests.append(quest)
        # Sortiert nach Automatisierbarkeit + Reward
        quests.sort(key=lambda q: (q.automatable, q.difficulty_score), reverse=True)
        return quests

    def get_quest_detail(self, campaign_id: str) -> dict:
        """Holt Detail-Infos fuer eine spezifische Kampagne."""
        query = """
        query($id: ID!) {
          campaign(id: $id) {
            id name description rewardType
            credentialGroups {
              credentials {
                id name credType referenceLink description
              }
            }
          }
        }"""
        return self._gql(query, {"id": campaign_id})

    def format_quest_list(self, quests: list[GalxeQuest], top_n: int = 10) -> str:
        lines = [
            "",
            "=" * 68,
            "  GALXE AKTIVE QUESTS (automatable zuerst)",
            "=" * 68,
        ]
        for i, q in enumerate(quests[:top_n], 1):
            auto_tag = "[AUTO]" if q.automatable else "[MAN] "
            lines.append(f"  {i:>2}. {auto_tag} {q.name[:45]:<45}")
            lines.append(f"       Reward: {q.reward_type:<10} | Tasks: {len(q.tasks)}")
            if q.tasks:
                for t in q.tasks[:2]:
                    lines.append(f"       - {t.get('type','?')}: {t.get('name','')[:40]}")
            lines.append("")
        lines.append("=" * 68)
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Internals                                                            #
    # ------------------------------------------------------------------ #

    def _fetch_campaigns(self, limit: int) -> list[dict]:
        # Cache pruefen
        now = time.time()
        if self._cache.get("ts", 0) + CACHE_TTL > now:
            return self._cache.get("data", [])
        if CACHE_FILE.exists():
            try:
                disk = json.loads(CACHE_FILE.read_text())
                if disk.get("ts", 0) + CACHE_TTL > now:
                    self._cache = disk
                    return disk.get("data", [])
            except Exception:
                pass

        query = f"""
        {{
          campaigns(input: {{first: {limit}, status: Active}}) {{
            list {{
              id name rewardType
              credentialGroups {{
                credentials {{
                  id name credType referenceLink description
                }}
              }}
            }}
          }}
        }}"""
        try:
            result = self._gql(query)
            campaigns = (
                result.get("data", {})
                .get("campaigns", {})
                .get("list", [])
            )
            self._cache = {"ts": now, "data": campaigns}
            CACHE_FILE.parent.mkdir(exist_ok=True)
            CACHE_FILE.write_text(json.dumps(self._cache))
            log.info(f"Galxe: {len(campaigns)} aktive Kampagnen geladen.")
            return campaigns
        except Exception as e:
            log.error(f"Galxe fetch: {e}")
            return self._cache.get("data", [])

    def _parse_campaign(self, camp: dict) -> GalxeQuest | None:
        try:
            tasks = []
            for grp in camp.get("credentialGroups", []):
                for cred in grp.get("credentials", []):
                    tasks.append({
                        "id":   cred.get("id", ""),
                        "name": cred.get("name", ""),
                        "type": cred.get("credType", "UNKNOWN"),
                        "ref":  cred.get("referenceLink", ""),
                        "desc": cred.get("description", ""),
                    })

            automatable_tasks     = [t for t in tasks if t["type"] in AUTOMATABLE_CRED_TYPES]
            non_automatable_tasks = [t for t in tasks if t["type"] in NON_AUTOMATABLE_CRED_TYPES]
            # Automatisierbar wenn: mind. 1 Task, keine nicht-automatisierbaren
            all_automatable = (
                len(tasks) > 0
                and len(non_automatable_tasks) == 0
                and len(automatable_tasks) > 0
            )
            difficulty = len(automatable_tasks) / max(1, len(tasks))

            return GalxeQuest(
                id           = camp["id"],
                name         = camp.get("name", "Unnamed"),
                url          = f"https://app.galxe.com/quest/{camp['id']}",
                reward_type  = camp.get("rewardType", "UNKNOWN"),
                tasks        = tasks,
                automatable  = all_automatable,
                difficulty_score = difficulty,
                estimated_eur = 2.0 if all_automatable else 0.5,
            )
        except Exception as e:
            log.debug(f"Parse campaign: {e}")
            return None

    def _gql(self, query: str, variables: dict | None = None) -> dict:
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables
        resp = requests.post(
            GRAPHQL_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent":   "Mozilla/5.0 (AirdropBot/1.0)",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
