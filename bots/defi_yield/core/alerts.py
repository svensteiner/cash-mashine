#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AlertSystem — Windows-Benachrichtigungen + Log-Alerts fuer den DeFi Bot.
"""
from __future__ import annotations
import logging, subprocess
from datetime import datetime

log = logging.getLogger("DeFi.Alerts")


class AlertSystem:
    def __init__(self, config: dict):
        self.min_apy = float(config.get("min_apy_threshold", 3.0))

    def check_and_alert(self, current_apy: float, best_apy: float, capital: float) -> list[str]:
        alerts = []
        if current_apy < self.min_apy:
            msg = f"APY ALARM: Dein aktueller APY {current_apy:.1f}% ist unter dem Minimum {self.min_apy:.1f}%!"
            alerts.append(msg)
            self._notify("DeFi Bot ALARM", msg)

        if best_apy > current_apy * 1.5:
            gain = capital * (best_apy - current_apy) / 100
            msg  = f"BESSERE YIELD: {best_apy:.1f}% verfuegbar (aktuell {current_apy:.1f}%). +{gain:.0f} EUR/Jahr moeglich!"
            alerts.append(msg)
            self._notify("DeFi Bot Tipp", msg)

        return alerts

    def compound_alert(self, rec: dict) -> None:
        if rec.get("should_compound"):
            self._notify(
                "DeFi Bot: Jetzt Compouden!",
                rec.get("recommendation", "Compound empfohlen"),
            )

    def daily_summary_alert(self, daily_eur: float, apy: float) -> None:
        self._notify(
            f"DeFi Bot: +{daily_eur:.4f} EUR heute",
            f"APY: {apy:.1f}% | Hochrechnung: {daily_eur*365:.0f} EUR/Jahr",
        )

    def _notify(self, title: str, message: str) -> None:
        """Windows-Benachrichtigung via PowerShell."""
        log.info(f"ALERT: {title} — {message}")
        try:
            script = (
                f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
                f"ContentType = WindowsRuntime] | Out-Null; "
                f"$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
                f"[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
                f"$template.SelectSingleNode('//text[@id=1]').InnerText = '{title}'; "
                f"$template.SelectSingleNode('//text[@id=2]').InnerText = '{message[:100]}'; "
                f"$toast = [Windows.UI.Notifications.ToastNotification]::new($template); "
                f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('DeFiBot').Show($toast);"
            )
            subprocess.run(
                ["powershell", "-WindowStyle", "Hidden", "-Command", script],
                capture_output=True, timeout=5,
            )
        except Exception as e:
            log.debug(f"Toast-Notification fehlgeschlagen: {e}")
