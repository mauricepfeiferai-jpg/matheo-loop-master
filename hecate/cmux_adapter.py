#!/usr/bin/env python3
"""cmux Notification Adapter — sendet Alerts an cmux (macOS Terminal).

cmux (https://cmux.com) zeigt Benachrichtigungen via OSC 9/99/777 an.
Auf einem headless Linux-Server schreiben wir zusätzlich in ein Log,
damit ein lokales cmux-Panel oder SSH-Wrapper die Alerts abholen kann.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

NOTIFY_LOG = Path("/var/lib/loop-master/cmux_notifications.jsonl")
RING_MAP = {
    "krit":   "🔴 KRITISCH",
    "hoch":   "🟠 HOCH",
    "mittel": "🟡 MITTEL",
    "info":   "🔵 INFO",
    "ok":     "🟢 OK",
}


def _osc9(message: str) -> str:
    """iTerm2 / cmux Notification OSC-Sequenz."""
    return f"\x1b]9;{message}\x07"


def _osc777(title: str, body: str) -> str:
    """Alternative OSC 777 Notification (cmux/vterm)."""
    payload = json.dumps({"title": title, "body": body})
    return f"\x1b]777;notify;{payload}\x07"


def enabled() -> bool:
    """Aktiv wenn explizit via Env oder Config eingeschaltet."""
    env = os.environ.get("CMUX_NOTIFY", "").lower()
    if env in ("1", "true", "yes"):
        return True
    if env in ("0", "false", "no"):
        return False
    try:
        from hecate.config import load_config
        cfg = load_config()
        return bool(cfg.get("escalation", {}).get("cmux", {}).get("enabled", False))
    except Exception:
        return False


def send_notification(
    level: str,
    subject: str,
    evidence: str = "",
    suggested_fix: str = "",
) -> bool:
    """Sendet cmux-Benachrichtigung (OSC + Log)."""
    if not enabled():
        return False

    label = RING_MAP.get(level, f"⚪ {level.upper()}")
    title = f"{label} · {subject}"
    body_lines = [evidence[:200]]
    if suggested_fix:
        body_lines.append(f"💡 {suggested_fix[:120]}")
    body = "\n".join(body_lines)

    # An aktives Terminal senden, falls vorhanden (SSH + cmux)
    try:
        if sys.stdout.isatty():
            sys.stdout.write(_osc9(title) + _osc777(title, body))
            sys.stdout.flush()
    except Exception:
        pass

    # Persistentes Log für cmux-Integration/Wrapper
    NOTIFY_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "subject": subject,
        "evidence": evidence[:200],
        "suggested_fix": suggested_fix[:120],
    }
    with open(NOTIFY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return True


if __name__ == "__main__":
    # Demo
    os.environ["CMUX_NOTIFY"] = "1"
    send_notification("krit", "Disk fast voll", "/ bei 91%", "Aufräumen")
    print("cmux notification sent")
