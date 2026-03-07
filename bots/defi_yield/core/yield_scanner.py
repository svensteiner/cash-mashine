#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YieldScanner — Scannt DeFi Llama API nach den besten Stablecoin-Yields.

Kein API-Key noetig. Gibt gefilterte, sortierte Pool-Liste zurueck.
"""
from __future__ import annotations
import json, logging, time
from datetime import datetime, UTC
from pathlib import Path
import requests

log = logging.getLogger("DeFi.YieldScanner")

LLAMA_URL  = "https://yields.llama.fi/pools"
CACHE_FILE = Path(__file__).parent.parent / "state" / "yield_cache.json"
CACHE_TTL  = 300  # 5 Minuten

# Anerkannte sichere Protokolle (TVL > 50M bestaetigt)
SAFE_PROTOCOLS = {
    "aave-v3", "aave-v2", "compound-v3", "compound-v2",
    "curve-dex", "yearn-finance", "spark", "morpho-blue",
    "fluid", "sky", "uniswap-v3",
}


class YieldScanner:
    def __init__(self, config: dict):
        self.min_tvl     = config.get("min_tvl_usd", 50_000_000)
        self.min_apy     = config.get("min_apy", 1.5)
        self.only_stable = config.get("only_stablecoins", True)
        self.safe_only   = config.get("safe_protocols_only", True)
        self._cache: dict = {}

    # ------------------------------------------------------------------ #

    def get_best_pools(self, chains: list[str] | None = None) -> list[dict]:
        """Gibt sortierte Pool-Liste zurueck (cached, max 5 Min alt)."""
        raw = self._fetch()
        pools = self._filter(raw, chains)
        pools.sort(key=lambda p: p["apy"], reverse=True)
        return pools

    def get_pool(self, protocol: str, chain: str, symbol_contains: str = "USDC") -> dict | None:
        """Sucht einen spezifischen Pool."""
        pools = self.get_best_pools([chain])
        for p in pools:
            if p["project"] == protocol and symbol_contains.upper() in p["symbol"].upper():
                return p
        return None

    def summary_table(self, pools: list[dict], top_n: int = 10) -> str:
        lines = [
            "",
            "=" * 72,
            "  BESTE STABLECOIN-YIELDS (Live von DeFi Llama)",
            f"  Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            "=" * 72,
            f"  {'Protokoll':<20} {'Symbol':<18} {'APY':>6}  {'TVL':>10}  Chain",
            "  " + "-" * 68,
        ]
        for p in pools[:top_n]:
            tvl_str = f"${p['tvlUsd']/1e6:.0f}M"
            lines.append(
                f"  {p['project']:<20} {p['symbol']:<18} "
                f"{p['apy']:>5.1f}%  {tvl_str:>10}  {p['chain']}"
            )
        lines.append("=" * 72)
        return "\n".join(lines)

    def earnings_preview(self, capital_eur: float, pools: list[dict], top_n: int = 5) -> str:
        lines = [
            "",
            f"  RENDITE-VORSCHAU fuer {capital_eur:,.0f} EUR Kapital",
            "  " + "-" * 55,
            f"  {'Protokoll':<20} {'APY':>6}  {'EUR/Tag':>8}  {'EUR/Jahr':>9}",
            "  " + "-" * 55,
        ]
        for p in pools[:top_n]:
            daily  = capital_eur * p["apy"] / 100 / 365
            yearly = capital_eur * p["apy"] / 100
            lines.append(
                f"  {p['project']:<20} {p['apy']:>5.1f}%"
                f"  {daily:>7.2f} EUR  {yearly:>8.0f} EUR"
            )
        lines.append("  " + "-" * 55)
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Internals                                                            #
    # ------------------------------------------------------------------ #

    def _fetch(self) -> list[dict]:
        """Holt Pool-Daten (mit 5-Min Cache)."""
        now = time.time()
        if self._cache.get("ts", 0) + CACHE_TTL > now:
            return self._cache.get("data", [])
        # Disk-Cache pruefen
        if CACHE_FILE.exists():
            try:
                disk = json.loads(CACHE_FILE.read_text())
                if disk.get("ts", 0) + CACHE_TTL > now:
                    self._cache = disk
                    log.debug("Yield-Cache aus Disk geladen.")
                    return disk["data"]
            except Exception:
                pass
        # API-Call
        try:
            log.info("DeFi Llama: Lade aktuelle Pool-Daten...")
            resp = requests.get(LLAMA_URL, timeout=20, headers={"User-Agent": "DeFiYieldBot/1.0"})
            resp.raise_for_status()
            data = resp.json()["data"]
            self._cache = {"ts": now, "data": data}
            CACHE_FILE.parent.mkdir(exist_ok=True)
            CACHE_FILE.write_text(json.dumps(self._cache))
            log.info(f"DeFi Llama: {len(data)} Pools geladen.")
            return data
        except Exception as e:
            log.error(f"DeFi Llama Fehler: {e}")
            return self._cache.get("data", [])

    def _filter(self, pools: list[dict], chains: list[str] | None) -> list[dict]:
        result = []
        for p in pools:
            if self.only_stable and not p.get("stablecoin"):
                continue
            if p.get("apy", 0) < self.min_apy:
                continue
            if p.get("tvlUsd", 0) < self.min_tvl:
                continue
            if self.safe_only and p.get("project") not in SAFE_PROTOCOLS:
                continue
            if chains and p.get("chain") not in chains:
                continue
            result.append(p)
        return result
