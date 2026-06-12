#!/usr/bin/env python3
"""Telegram Commands — /status, /sensors, /findings, /dashboard, /ack.

Verarbeitet Commands von Maurice im Chat.
"""
import json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hecate.telegram_enhanced import (
    send_message, send_photo, format_snapshot, format_findings,
    format_sensor_card, sensor_keyboard, ack_keyboard
)
from hecate.memory_store import get_profile, log_decision

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

def cmd_status():
    from hecate_bridge import snapshot
    data = snapshot()
    text = format_snapshot(data)
    send_message(text)

def cmd_sensors():
    from hecate_bridge import sensor_status
    sensors = sensor_status()
    lines = ["*Sensoren Status*\n"]
    for s in sensors:
        lines.append(format_sensor_card(s))
    kb = sensor_keyboard(sensors)
    send_message("\n".join(lines), keyboard=kb)

def cmd_findings(n: str = "5"):
    from hecate_bridge import read_bus
    try:
        n = int(n)
    except:
        n = 5
    findings = read_bus(n)
    text = format_findings(findings, n)
    send_message(text)

def cmd_dashboard():
    from hecate.browser import screenshot
    path = screenshot("http://localhost:8877")
    if path and Path(path).exists():
        send_photo(path, caption="🌑 Hecate Dashboard")
    else:
        send_message("Dashboard Screenshot fehlgeschlagen\. [Link](http://localhost:8877)")

def cmd_ack(subject: str = ""):
    from hecate.ledger import Ledger
    # Mark finding as acknowledged
    send_message(f"✅ ACK: `{subject}`")

def cmd_help():
    text = (
        "*Hecate Commands*\n\n"
        "/status — System Snapshot\n"
        "/sensors — Alle Sensoren + Alerts\n"
        "/findings [n] — Letzte n Findings\n"
        "/dashboard — Screenshot\n"
        "/ack <subject> — Bestätigen\n"
        "/help — Diese Hilfe\n\n"
        "_Autonom: L1-L2, nach GO: L3-L5_"
    )
    send_message(text)

COMMANDS = {
    "/status": cmd_status,
    "/sensors": cmd_sensors,
    "/findings": lambda: cmd_findings(sys.argv[2] if len(sys.argv) > 2 else "5"),
    "/dashboard": cmd_dashboard,
    "/ack": lambda: cmd_ack(sys.argv[2] if len(sys.argv) > 2 else ""),
    "/help": cmd_help,
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("telegram_commands.py <command> [arg]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        send_message(f"Unbekannter Befehl: `{cmd}`\. Versuche /help")
