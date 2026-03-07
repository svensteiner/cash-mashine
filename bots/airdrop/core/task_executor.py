#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TaskExecutor — Fuehrt Quest-Tasks automatisch aus.

Unterstuetzt:
  TWITTER_FOLLOW   → Playwright navigiert zu Twitter, klickt Follow
  TWITTER_RETWEET  → Retweet via Twitter URL
  TWITTER_LIKE     → Like via Twitter URL
  DISCORD_MEMBER   → Tritt Discord-Server bei
  QUIZ / GALXE_QUIZ → LLM beantwortet Fragen
  VISIT_LINK       → Oeffnet URL (viele Plattformen tracken das)

Geerbt vom MarketingBot: Playwright CDP/Persistent Pattern.
"""
from __future__ import annotations
import logging, time, re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("Airdrop.TaskExecutor")

ROOT = Path(__file__).parent.parent


@dataclass
class TaskResult:
    task_type: str
    success: bool
    message: str = ""
    skipped: bool = False


class TaskExecutor:
    def __init__(self, config: dict, llm_client=None):
        self.config     = config
        self.llm        = llm_client
        self.llm_model  = config.get("model", "openai/gpt-4o-mini")
        self._page      = None
        self._pw        = None
        self._ctx       = None

    # ------------------------------------------------------------------ #
    # Browser Lifecycle                                                    #
    # ------------------------------------------------------------------ #

    def start_browser(self) -> bool:
        try:
            from playwright.sync_api import sync_playwright
            self._pw  = sync_playwright().start()
            mode      = self.config.get("browser_mode", "persistent")
            if mode == "cdp":
                port          = self.config.get("cdp_port", 9225)
                self._browser = self._pw.chromium.connect_over_cdp(f"http://localhost:{port}")
                ctx           = self._browser.contexts[0]
                self._page    = ctx.pages[0] if ctx.pages else ctx.new_page()
            else:
                data_dir   = ROOT / "browser_data"
                self._ctx  = self._pw.chromium.launch_persistent_context(
                    str(data_dir),
                    headless=False,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                    locale="de-DE",
                    viewport={"width": 1280, "height": 800},
                )
                self._page = (
                    self._ctx.pages[0] if self._ctx.pages
                    else self._ctx.new_page()
                )
            log.info(f"Browser gestartet (Modus: {mode})")
            return True
        except Exception as e:
            log.error(f"Browser-Start: {e}")
            return False

    def stop_browser(self) -> None:
        try:
            if self._ctx:
                self._ctx.close()
            elif hasattr(self, "_browser"):
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Task Dispatcher                                                      #
    # ------------------------------------------------------------------ #

    def execute(self, task: dict) -> TaskResult:
        t = task.get("type", "UNKNOWN")
        log.info(f"Executing task: {t} — {task.get('name', '')[:40]}")
        try:
            # Galxe fasst alle Twitter-Tasks unter "TWITTER" zusammen —
            # Typ aus dem Namen ableiten
            if t in ("TWITTER", "TWITTER_FOLLOW", "TWITTER_RETWEET",
                     "TWITTER_LIKE", "TWITTER_TWEET"):
                return self._dispatch_twitter(task)
            elif t in ("DISCORD", "DISCORD_MEMBER"):
                return self._discord_join(task)
            elif t in ("QUIZ", "GALXE_QUIZ"):
                return self._solve_quiz(task)
            elif t in ("VISIT_LINK", "GALXE_ID"):
                return self._visit_link(task)
            else:
                return TaskResult(t, False, f"Task-Typ '{t}' nicht implementiert", skipped=True)
        except Exception as e:
            log.error(f"Task {t} Exception: {e}")
            return TaskResult(t, False, str(e))

    # ------------------------------------------------------------------ #
    # Twitter Tasks                                                        #
    # ------------------------------------------------------------------ #

    def _dispatch_twitter(self, task: dict) -> TaskResult:
        """Erkennt anhand des Task-Namens was zu tun ist."""
        name = task.get("name", "").lower()
        if "follower" in name or "follow" in name:
            return self._twitter_follow(task)
        elif "retweet" in name or "retweeter" in name:
            return self._twitter_retweet(task)
        elif "liker" in name or "like" in name:
            return self._twitter_like(task)
        elif "quot" in name:
            return self._twitter_retweet(task)  # Quote-Tweet wie Retweet behandeln
        elif "tweet" in name:
            return self._twitter_tweet(task)
        else:
            # Fallback: versuche Follow wenn Ref ein Twitter-Profil ist
            ref = task.get("ref", "")
            if ref and ("twitter.com" in ref or "x.com" in ref):
                if "/status/" in ref:
                    return self._twitter_like(task)
                return self._twitter_follow(task)
            return TaskResult("TWITTER", False, f"Twitter-Subtyp unklar: {name[:40]}", skipped=True)

    def _twitter_follow(self, task: dict) -> TaskResult:
        ref = task.get("ref", "")
        # Twitter-Handle aus URL extrahieren
        handle = self._extract_twitter_handle(ref)
        if not handle:
            return TaskResult("TWITTER_FOLLOW", False, f"Kein Handle gefunden in: {ref}")

        page = self._page
        url  = f"https://twitter.com/{handle}"
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)

        try:
            # Follow-Button suchen
            btn = page.locator(
                'button[data-testid="follow"], '
                'div[data-testid="placementTracking"] button:has-text("Follow")'
            ).first
            if btn.is_visible(timeout=5000):
                btn.click()
                time.sleep(1)
                log.info(f"Twitter Follow: @{handle}")
                return TaskResult("TWITTER_FOLLOW", True, f"Folge jetzt @{handle}")
            else:
                # Vielleicht schon gefolgt
                following = page.locator('button[data-testid="unfollow"]').first
                if following.is_visible(timeout=2000):
                    return TaskResult("TWITTER_FOLLOW", True, f"Folge bereits @{handle}", skipped=True)
                return TaskResult("TWITTER_FOLLOW", False, "Follow-Button nicht gefunden")
        except Exception as e:
            return TaskResult("TWITTER_FOLLOW", False, str(e))

    def _twitter_retweet(self, task: dict) -> TaskResult:
        ref = task.get("ref", "")
        if not ref or "twitter.com" not in ref and "x.com" not in ref:
            return TaskResult("TWITTER_RETWEET", False, "Kein Tweet-URL")

        page = self._page
        page.goto(ref, wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)

        try:
            rt_btn = page.locator('[data-testid="retweet"]').first
            if rt_btn.is_visible(timeout=5000):
                rt_btn.click()
                time.sleep(1)
                # Bestaetigungs-Dialog
                confirm = page.locator('[data-testid="retweetConfirm"]').first
                if confirm.is_visible(timeout=3000):
                    confirm.click()
                    time.sleep(1)
                return TaskResult("TWITTER_RETWEET", True, "Retweeted")
            return TaskResult("TWITTER_RETWEET", False, "Retweet-Button nicht gefunden")
        except Exception as e:
            return TaskResult("TWITTER_RETWEET", False, str(e))

    def _twitter_like(self, task: dict) -> TaskResult:
        ref = task.get("ref", "")
        if not ref:
            return TaskResult("TWITTER_LIKE", False, "Kein Tweet-URL")

        page = self._page
        page.goto(ref, wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)

        try:
            like_btn = page.locator('[data-testid="like"]').first
            if like_btn.is_visible(timeout=5000):
                like_btn.click()
                time.sleep(1)
                return TaskResult("TWITTER_LIKE", True, "Geliked")
            # Schon geliked?
            unlike = page.locator('[data-testid="unlike"]').first
            if unlike.is_visible(timeout=2000):
                return TaskResult("TWITTER_LIKE", True, "Bereits geliked", skipped=True)
            return TaskResult("TWITTER_LIKE", False, "Like-Button nicht gefunden")
        except Exception as e:
            return TaskResult("TWITTER_LIKE", False, str(e))

    def _twitter_tweet(self, task: dict) -> TaskResult:
        """Schreibt einen Tweet (nutzt LLM fuer Text-Generierung)."""
        desc = task.get("desc", task.get("name", ""))
        if self.llm:
            try:
                resp = self.llm.chat.completions.create(
                    model=self.llm_model,
                    messages=[{
                        "role": "user",
                        "content": f"Schreibe einen kurzen, enthusiastischen Tweet (max 250 Zeichen) fuer diese Quest-Aufgabe: {desc}. Nur den Tweet-Text, keine Erklaerung."
                    }],
                    max_tokens=100,
                )
                tweet_text = resp.choices[0].message.content.strip()
            except Exception:
                tweet_text = f"Excited to participate! #{desc[:30]}"
        else:
            tweet_text = f"Participating in this amazing quest! #Web3 #DeFi"

        page = self._page
        page.goto("https://twitter.com/compose/tweet", wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)
        try:
            editor = page.locator('[data-testid="tweetTextarea_0"]').first
            editor.click()
            editor.type(tweet_text, delay=30)
            time.sleep(1)
            send = page.locator('[data-testid="tweetButtonInline"]').first
            send.click()
            time.sleep(2)
            return TaskResult("TWITTER_TWEET", True, f"Tweet gesendet: {tweet_text[:50]}")
        except Exception as e:
            return TaskResult("TWITTER_TWEET", False, str(e))

    # ------------------------------------------------------------------ #
    # Discord Tasks                                                        #
    # ------------------------------------------------------------------ #

    def _discord_join(self, task: dict) -> TaskResult:
        ref = task.get("ref", "")
        if not ref or "discord" not in ref.lower():
            return TaskResult("DISCORD_MEMBER", False, "Kein Discord-Link")

        page = self._page
        # Discord Invite-Link oeffnen
        invite_url = ref if "discord.gg" in ref or "discord.com/invite" in ref else ref
        page.goto(invite_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)

        try:
            # "Server beitreten" Button
            join_btn = page.locator(
                'button:has-text("Join Server"), '
                'button:has-text("Accept Invite"), '
                'button:has-text("Einladen annehmen")'
            ).first
            if join_btn.is_visible(timeout=5000):
                join_btn.click()
                time.sleep(2)
                return TaskResult("DISCORD_MEMBER", True, f"Discord Server beigetreten: {ref[:40]}")
            # Vielleicht schon Mitglied
            return TaskResult("DISCORD_MEMBER", True, "Bereits Mitglied oder Login erforderlich", skipped=True)
        except Exception as e:
            return TaskResult("DISCORD_MEMBER", False, str(e))

    # ------------------------------------------------------------------ #
    # Quiz Tasks                                                           #
    # ------------------------------------------------------------------ #

    def _solve_quiz(self, task: dict) -> TaskResult:
        """Loest Quiz-Fragen mit LLM."""
        desc = task.get("desc", task.get("name", ""))
        if not self.llm:
            return TaskResult("QUIZ", False, "LLM nicht verfuegbar", skipped=True)

        try:
            resp = self.llm.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "Du bist ein Krypto/DeFi-Experte. Beantworte Quiz-Fragen praesize und kurz auf Englisch."},
                    {"role": "user",   "content": f"Quiz-Aufgabe: {desc}\n\nWas ist die richtige Antwort? Gib nur die Antwort, keine Erklaerung."}
                ],
                max_tokens=50,
            )
            answer = resp.choices[0].message.content.strip()
            log.info(f"Quiz-Antwort: {answer}")
            return TaskResult("QUIZ", True, f"LLM-Antwort: {answer}")
        except Exception as e:
            return TaskResult("QUIZ", False, str(e))

    # ------------------------------------------------------------------ #
    # Visit Link                                                           #
    # ------------------------------------------------------------------ #

    def _visit_link(self, task: dict) -> TaskResult:
        ref = task.get("ref", "")
        if not ref:
            return TaskResult("VISIT_LINK", False, "Kein Link")
        page = self._page
        page.goto(ref, wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)  # Seite muss geladen sein damit Tracker registriert
        return TaskResult("VISIT_LINK", True, f"Besucht: {ref[:50]}")

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _extract_twitter_handle(self, text: str) -> str:
        patterns = [
            r"twitter\.com/([A-Za-z0-9_]+)",
            r"x\.com/([A-Za-z0-9_]+)",
            r"@([A-Za-z0-9_]+)",
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                handle = m.group(1)
                if handle.lower() not in ("intent", "share", "home", "i"):
                    return handle
        return ""
