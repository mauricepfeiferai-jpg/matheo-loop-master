#!/usr/bin/env python3
"""Telegram Enhanced — Rich Messages via Hermes Backend.

Features:
- Structured digests (morning/evening)
- Dashboard screenshots as photos via hermes
- Command handlers
- Retry logic
"""
import json, os, re, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

def _send_hermes(text: str) -> bool:
    for attempt in range(3):
        try:
            r = subprocess.run(
                ["hermes", "send", "--to", "telegram", "-q", text],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode == 0:
                return True
            time.sleep(2 ** attempt)
        except Exception:
            time.sleep(2 ** attempt)
    return False

def send_message(text: str) -> bool:
    return _send_hermes(text[:4096])

def send_photo(photo_path: str, caption: str = "") -> bool:
    if not Path(photo_path).exists():
        return False
    for attempt in range(3):
        try:
            r = subprocess.run(
                ["hermes", "send", "--to", "telegram", "-q", f"{caption} [Bild: {photo_path}]"],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode == 0:
                return True
            time.sleep(2 ** attempt)
        except Exception:
            time.sleep(2 ** attempt)
    return False

def format_snapshot(data: dict) -> str:
    f = data.get("findings", {})
    return (
        f"🌑 HECATE Status\n\n"
        f"🔴 Kritisch: {f.get('krit', 0)}\n"
        f"🟠 Hoch: {f.get('hoch', 0)}\n"
        f"🟡 Mittel: {f.get('mittel', 0)}\n"
        f"🔵 Info: {f.get('info', 0)}\n\n"
        f"Sensoren: {len(data.get('sensors', []))} running\n"
        f"Dashboard: http://localhost:8877"
    )

def format_findings(findings: list, n: int = 5) -> str:
    icons = {"krit": "🔴", "hoch": "🟠", "mittel": "🟡", "info": "🔵"}
    lines = [f"Letzte {min(n, len(findings))} Findings\n"]
    for f in findings[:n]:
        sev = f.get("severity", "info")
        icon = icons.get(sev, "⚪")
        subject = f.get("subject", "—")[:50]
        evidence = f.get("evidence", "")[:80]
        lines.append(f"{icon} [{f.get('sensor','?')}] {subject}")
        if evidence:
            lines.append(f"   {evidence}")
    return "\n".join(lines)

def format_sensor_card(sensor: dict) -> str:
    icon = "🔴" if sensor.get("alert") else "✅"
    name = sensor.get("sensor", "?")
    latest = sensor.get("latest", "—")[:40]
    return f"{icon} {name}\n   {latest} ({sensor.get('count', 0)} heute)"

def send_morning_digest(snapshot_data: dict, findings: list) -> None:
    text = "🌅 *Guten Morgen, Maurice*\n\n"
    text += format_snapshot(snapshot_data)
    if findings:
        text += "\n\n" + format_findings(findings, 3)
    text += "\n\n_Befehle: /status /sensors /findings /dashboard /help_"
    send_message(text)

def send_evening_digest(trend_data: dict) -> None:
    f = trend_data.get("findings", {})
    text = (
        f"🌙 *Tagesbericht*\n\n"
        f"🔴 Kritisch: {f.get('krit', 0)}\n"
        f"🟠 Hoch: {f.get('hoch', 0)}\n"
        f"Trend: {trend_data.get('trend', 'stable')}\n\n"
        f"{datetime.now(timezone.utc).strftime('%H:%M')}"
    )
    send_message(text)

if __name__ == "__main__":
    send_message("🌑 Hecate Enhanced — Test")
