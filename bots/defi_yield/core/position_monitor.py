#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PositionMonitor — Verfolgt deine DeFi-Position via Etherscan/Arbiscan API.

Liest Wallet-Balance, Token-Holdings und historische Transaktionen.
Kein Private Key noetig — nur deine Wallet-Adresse (read-only).
"""
from __future__ import annotations
import json, logging, os, time
from datetime import datetime, UTC
from pathlib import Path
import requests

log = logging.getLogger("DeFi.PositionMonitor")

STATE_FILE = Path(__file__).parent.parent / "state" / "position.json"

# Bekannte Token-Adressen (Ethereum Mainnet)
STABLECOIN_TOKENS = {
    "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": ("USDC",   6),
    "0xdAC17F958D2ee523a2206206994597C13D831ec7": ("USDT",   6),
    "0x6B175474E89094C44Da98b954EedeAC495271d0F": ("DAI",   18),
    # aTokens (Aave)
    "0xBcca60bB61934080951369a648Fb03DF4F96263C": ("aUSDC",  6),
    "0x3Ed3B47Dd13EC9a98b44e6204A523E4Cc1C5B0": ("aUSDT",   6),
}

CHAINS = {
    "Ethereum": {
        "api":     "https://api.etherscan.io/api",
        "api_key": "ETHERSCAN_API_KEY",
        "symbol":  "ETH",
    },
    "Arbitrum": {
        "api":     "https://api.arbiscan.io/api",
        "api_key": "ARBISCAN_API_KEY",
        "symbol":  "ETH",
    },
    "Base": {
        "api":     "https://api.basescan.org/api",
        "api_key": "BASESCAN_API_KEY",
        "symbol":  "ETH",
    },
}


class PositionMonitor:
    def __init__(self, config: dict):
        self.wallet   = config.get("wallet_address", "").strip()
        self.chain    = config.get("target_chain", "Arbitrum")
        self.capital  = float(config.get("capital_eur", 5000))
        self._history: list = self._load_history()

    def is_configured(self) -> bool:
        return bool(self.wallet and self.wallet.startswith("0x") and len(self.wallet) == 42)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def get_snapshot(self) -> dict:
        """Aktuelle Wallet-Position auf der konfigurierten Chain."""
        if not self.is_configured():
            return {"error": "Wallet-Adresse nicht konfiguriert in .env"}

        chain_cfg = CHAINS.get(self.chain, CHAINS["Ethereum"])
        api_key   = os.environ.get(chain_cfg["api_key"], "")
        base_url  = chain_cfg["api"]

        snap = {
            "timestamp": datetime.now(UTC).isoformat(),
            "wallet":    self.wallet,
            "chain":     self.chain,
            "eth_balance": self._get_eth_balance(base_url, api_key),
            "tokens":      self._get_token_balances(base_url, api_key),
            "total_stable_usd": 0.0,
        }
        # Summe der Stablecoins berechnen
        snap["total_stable_usd"] = sum(
            t["balance_usd"] for t in snap["tokens"].values()
            if t.get("is_stable")
        )
        self._save_snapshot(snap)
        return snap

    def get_earnings_estimate(self, current_apy: float) -> dict:
        """Schaetzt heutige Einnahmen basierend auf APY und Kapital."""
        daily_rate  = current_apy / 100 / 365
        daily_eur   = self.capital * daily_rate
        weekly_eur  = daily_eur * 7
        monthly_eur = daily_eur * 30
        yearly_eur  = self.capital * current_apy / 100

        return {
            "apy_pct":      current_apy,
            "capital_eur":  self.capital,
            "daily_eur":    round(daily_eur, 4),
            "weekly_eur":   round(weekly_eur, 3),
            "monthly_eur":  round(monthly_eur, 2),
            "yearly_eur":   round(yearly_eur, 2),
        }

    def compound_recommendation(self, apy: float, gas_usd: float) -> dict:
        """Berechnet ob und wann compounding sich lohnt."""
        daily_yield_usd = self.capital * apy / 100 / 365
        # Break-even: Wie viele Tage bis Gas-Kosten reingeholt?
        days_to_break_even = gas_usd / daily_yield_usd if daily_yield_usd > 0 else 999
        # Compounding lohnt sich wenn Gas < 10% der wchentlichen Rewards
        weekly_yield = daily_yield_usd * 7
        should_compound = gas_usd < weekly_yield * 0.1

        return {
            "should_compound":      should_compound,
            "gas_usd":              gas_usd,
            "daily_yield_usd":      round(daily_yield_usd, 4),
            "days_to_break_even":   round(days_to_break_even, 1),
            "recommendation":       (
                f"COMPOUND JETZT (Gas wird in {days_to_break_even:.0f} Tagen reingeholt)"
                if should_compound else
                f"WARTEN (Gas {gas_usd:.2f} USD > 10% Weekly Rewards {weekly_yield*0.1:.2f} USD)"
            ),
        }

    def format_snapshot(self, snap: dict, earnings: dict) -> str:
        ts = snap.get("timestamp", "")[:16].replace("T", " ")
        lines = [
            "",
            "=" * 62,
            f"  POSITION SNAPSHOT — {ts}",
            f"  Wallet: {snap.get('wallet', '?')[:20]}...",
            f"  Chain:  {snap.get('chain', '?')}",
            "=" * 62,
        ]
        eth = snap.get("eth_balance", 0)
        lines.append(f"  ETH Balance:    {eth:.6f} ETH")
        tokens = snap.get("tokens", {})
        if tokens:
            lines.append("  Token-Balances:")
            for sym, info in tokens.items():
                lines.append(
                    f"    {sym:<10} {info['balance']:>12.2f}  "
                    f"(~${info.get('balance_usd', 0):.2f})"
                )
        stable = snap.get("total_stable_usd", 0)
        lines.append(f"  Stablecoin Gesamt: ${stable:,.2f}")
        lines.append("")
        lines.append(f"  RENDITE bei {earnings['apy_pct']:.1f}% APY:")
        lines.append(f"    Heute:   {earnings['daily_eur']:.4f} EUR")
        lines.append(f"    Woche:   {earnings['weekly_eur']:.3f} EUR")
        lines.append(f"    Monat:   {earnings['monthly_eur']:.2f} EUR")
        lines.append(f"    Jahr:    {earnings['yearly_eur']:.2f} EUR")
        lines.append("=" * 62)
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Internals                                                            #
    # ------------------------------------------------------------------ #

    def _get_eth_balance(self, base_url: str, api_key: str) -> float:
        if not api_key or api_key == "YourEtherscanKeyHere":
            return 0.0
        try:
            resp = requests.get(base_url, params={
                "module": "account", "action": "balance",
                "address": self.wallet, "tag": "latest",
                "apikey": api_key,
            }, timeout=10)
            data = resp.json()
            return int(data.get("result", 0)) / 1e18
        except Exception as e:
            log.debug(f"ETH Balance Fehler: {e}")
            return 0.0

    def _get_token_balances(self, base_url: str, api_key: str) -> dict:
        if not api_key or api_key == "YourEtherscanKeyHere":
            return {}
        result = {}
        for addr, (symbol, decimals) in STABLECOIN_TOKENS.items():
            try:
                resp = requests.get(base_url, params={
                    "module": "account", "action": "tokenbalance",
                    "contractaddress": addr, "address": self.wallet,
                    "tag": "latest", "apikey": api_key,
                }, timeout=10)
                raw = int(resp.json().get("result", 0))
                balance = raw / (10 ** decimals)
                if balance > 0.01:
                    result[symbol] = {
                        "balance":     round(balance, 4),
                        "balance_usd": round(balance, 2),
                        "is_stable":   True,
                    }
            except Exception as e:
                log.debug(f"Token {symbol} Fehler: {e}")
        return result

    def _save_snapshot(self, snap: dict) -> None:
        STATE_FILE.parent.mkdir(exist_ok=True)
        history = self._history[-29:]  # Letzte 30 Snapshots
        history.append(snap)
        STATE_FILE.write_text(json.dumps({"snapshots": history}, indent=2))
        self._history = history

    def _load_history(self) -> list:
        try:
            if STATE_FILE.exists():
                return json.loads(STATE_FILE.read_text()).get("snapshots", [])
        except Exception:
            pass
        return []
