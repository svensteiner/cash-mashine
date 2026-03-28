#!/usr/bin/env python
# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
from pathlib import Path

data_dir = Path(__file__).parent / "browser_data"
data_dir.mkdir(exist_ok=True)

pw = sync_playwright().start()
ctx = pw.chromium.launch_persistent_context(
    str(data_dir),
    headless=False,
    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
    locale="de-DE",
    viewport={"width": 1280, "height": 800},
)
page = ctx.pages[0] if ctx.pages else ctx.new_page()
page.goto("https://app.galxe.com")
print("Browser offen -- bitte auf allen 3 Seiten einloggen.")
print("Dieses Fenster schliessen wenn fertig.")
try:
    ctx.wait_for_event("close", timeout=600000)
except Exception:
    pass
try:
    ctx.close()
except Exception:
    pass
pw.stop()
print("Profil gespeichert.")
