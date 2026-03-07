#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FaucetClaimer — Playwright-basierter Browser-Claimer fuer Faucets.

Strategie:
  1. Oeffnet Faucet-URL im Browser
  2. Fuellt Wallet-Adresse ein
  3. Wartet auf CAPTCHA (manuell oder auto-geloest)
  4. Klickt Claim-Button
  5. Liest Reward aus

Geerbt vom MarketingBot: CDP-Verbindung zu bestehendem Chrome.
"""
from __future__ import annotations
import logging, os, time
from pathlib import Path

log = logging.getLogger("Faucet.Claimer")

ROOT = Path(__file__).parent.parent

# CAPTCHA-Timeout: Wie lange wartet der Bot auf manuelle Loesung?
CAPTCHA_WAIT_SECS = 30


class ClaimResult:
    def __init__(self, success: bool, amount: float = 0, crypto: str = "",
                 amount_usd: float = 0, message: str = ""):
        self.success    = success
        self.amount     = amount
        self.crypto     = crypto
        self.amount_usd = amount_usd
        self.message    = message

    def __repr__(self):
        if self.success:
            return f"ClaimResult(OK, +{self.amount} {self.crypto})"
        return f"ClaimResult(FAIL, {self.message})"


class FaucetClaimer:
    """
    Browser-Claimer. Unterstuetzt:
    - Direkter Launch (Playwright Persistent Context)
    - CDP-Verbindung zu laufendem Chrome (wie MarketingBot)
    """

    def __init__(self, config: dict, wallets: dict):
        self.config  = config
        self.wallets = wallets
        self.mode    = config.get("browser_mode", "persistent")  # persistent | cdp
        self.cdp_port = config.get("cdp_port", 9224)
        self._browser = None
        self._page    = None

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def start(self) -> bool:
        try:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            if self.mode == "cdp":
                self._browser = self._pw.chromium.connect_over_cdp(
                    f"http://localhost:{self.cdp_port}"
                )
                ctx = self._browser.contexts[0]
                self._page = ctx.pages[0] if ctx.pages else ctx.new_page()
            else:
                data_dir = ROOT / "browser_data"
                ctx = self._pw.chromium.launch_persistent_context(
                    str(data_dir),
                    headless=False,
                    args=["--disable-blink-features=AutomationControlled"],
                    locale="de-DE",
                )
                self._page = ctx.pages[0] if ctx.pages else ctx.new_page()
                self._ctx  = ctx
            log.info(f"Browser gestartet (Modus: {self.mode})")
            return True
        except Exception as e:
            log.error(f"Browser-Start fehlgeschlagen: {e}")
            return False

    def stop(self) -> None:
        try:
            if hasattr(self, "_ctx"):
                self._ctx.close()
            elif self._browser:
                self._browser.close()
            if hasattr(self, "_pw"):
                self._pw.stop()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Claim-Dispatcher                                                     #
    # ------------------------------------------------------------------ #

    def claim(self, faucet: dict) -> ClaimResult:
        """Dispatcht zum passenden Claimer basierend auf Faucet-ID."""
        fid = faucet.get("id", "")
        wallet = self.wallets.get(faucet.get("crypto", "ETH"), "")
        if not wallet:
            return ClaimResult(False, message=f"Keine Wallet fuer {faucet.get('crypto')}")

        log.info(f"Claiming: {faucet['name']} ({fid})")
        try:
            if fid == "cointiply":
                return self._claim_cointiply(faucet, wallet)
            elif fid == "freebitcoin":
                return self._claim_freebitcoin(faucet, wallet)
            elif fid == "firefaucet":
                return self._claim_firefaucet(faucet, wallet)
            elif fid == "dutchycorp":
                return self._claim_dutchycorp(faucet, wallet)
            else:
                return self._claim_generic(faucet, wallet)
        except Exception as e:
            log.error(f"Claim {fid} Exception: {e}")
            return ClaimResult(False, message=str(e))

    # ------------------------------------------------------------------ #
    # Spezifische Claimer                                                  #
    # ------------------------------------------------------------------ #

    def _claim_cointiply(self, faucet: dict, wallet: str) -> ClaimResult:
        page = self._page
        page.goto(faucet["url"], wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)

        # Login-Status pruefen
        if "login" in page.url.lower():
            log.warning("Cointiply: Login erforderlich — bitte manuell einloggen!")
            return ClaimResult(False, message="Login erforderlich")

        # Faucet-Button suchen
        try:
            btn = page.locator("button:has-text('Collect'), button:has-text('Claim'), input[type=submit]").first
            if btn.is_visible():
                # CAPTCHA-Wartezeit
                log.info("Cointiply: Warte auf CAPTCHA-Loesung...")
                time.sleep(CAPTCHA_WAIT_SECS)
                btn.click()
                time.sleep(3)
                # Ergebnis auslesen
                result_text = page.locator(".alert-success, .reward, .coins-earned").first.text_content(timeout=5000)
                log.info(f"Cointiply Result: {result_text}")
                return ClaimResult(True, crypto="BTC", amount_usd=0.001, message=result_text)
        except Exception as e:
            log.debug(f"Cointiply claim: {e}")
        return ClaimResult(False, message="Claim-Button nicht gefunden")

    def _claim_freebitcoin(self, faucet: dict, wallet: str) -> ClaimResult:
        page = self._page
        page.goto(faucet["url"], wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        try:
            # Roll-Button (FreeBitcoin nutzt einen "ROLL" Button)
            roll_btn = page.locator("#free_play_btn, button:has-text('ROLL')").first
            if roll_btn.is_visible():
                log.info("FreeBitcoin: Warte auf CAPTCHA...")
                time.sleep(CAPTCHA_WAIT_SECS)
                roll_btn.click()
                time.sleep(5)
                # Reward auslesen
                reward = page.locator("#winnings, .winnings, #free_play_result").first
                if reward.is_visible():
                    val = reward.text_content()
                    log.info(f"FreeBitcoin Result: {val}")
                    return ClaimResult(True, crypto="BTC", amount_usd=0.0005, message=val)
        except Exception as e:
            log.debug(f"FreeBitcoin: {e}")
        return ClaimResult(False, message="Claim fehlgeschlagen")

    def _claim_firefaucet(self, faucet: dict, wallet: str) -> ClaimResult:
        page = self._page
        page.goto(faucet["url"], wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        log.info("FireFaucet: Prueffe Auto-Claim Status...")
        # FireFaucet hat ein Auto-Claim Feature fuer angemeldete User
        try:
            status = page.locator(".autoclaim-status, .balance").first
            if status.is_visible():
                return ClaimResult(True, crypto="MULTI", amount_usd=0.002, message="AutoClaim aktiv")
        except Exception as e:
            log.debug(f"FireFaucet: {e}")
        return ClaimResult(False, message="Status nicht lesbar — manueller Check noetig")

    def _claim_dutchycorp(self, faucet: dict, wallet: str) -> ClaimResult:
        page = self._page
        page.goto(faucet["url"], wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        try:
            claim_btn = page.locator("button:has-text('Claim'), input[value='Claim']").first
            if claim_btn.is_visible():
                time.sleep(CAPTCHA_WAIT_SECS)
                claim_btn.click()
                time.sleep(3)
                return ClaimResult(True, crypto="MULTI", amount_usd=0.001)
        except Exception as e:
            log.debug(f"DutchyCorp: {e}")
        return ClaimResult(False, message="Claim fehlgeschlagen")

    def _claim_generic(self, faucet: dict, wallet: str) -> ClaimResult:
        """Generischer Claimer fuer unbekannte Faucets."""
        page = self._page
        page.goto(faucet["url"], wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        log.info(f"Generic Claimer fuer {faucet['name']} — manuelles Eingreifen moeglich noetig")
        return ClaimResult(False, message="Generischer Claimer — manuelle Konfiguration noetig")
