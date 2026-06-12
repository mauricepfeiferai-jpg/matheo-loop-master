"""Notification-Rings — Priorisierte Telegram-Alerts aus Hecate.
Übersetzt severity → Emoji + Farbe + Ton (für MauriceAI-Jarvis)."""

import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

# Prioritäts-Ring-Map (cmux-Konzept: blauer Ring = Aufmerksamkeit)
RING_MAP = {
    "krit":   ("🔴", "KRITISCH", "sofort"),
    "hoch":   ("🟠", "HOCH",     "1h"),
    "mittel": ("🟡", "MITTEL",   "4h"),
    "info":   ("🔵", "INFO",     "24h"),
    "ok":     ("🟢", "OK",       "—"),
}


def format_ring(level: str, subject: str, evidence: str, suggested_fix: str = "") -> str:
    """Formattiert ein Finding als cmux-style Notification-Ring."""
    emoji, label, sla = RING_MAP.get(level, ("⚪", "UNBEKANNT", "?"))
    lines = [
        f"{emoji} {label} · {subject}",
        f"   {evidence[:200]}",
    ]
    if suggested_fix:
        lines.append(f"   💡 {suggested_fix[:120]}")
    lines.append(f"   ⏱ SLA: {sla}")
    return "\n".join(lines)


def send_ring(level: str, subject: str, evidence: str, suggested_fix: str = "", token: str | None = None, chat_id: str | None = None) -> bool:
    """Sendet einen Ring an Telegram (jarvis-Kanal via hermes)."""
    text = format_ring(level, subject, evidence, suggested_fix)

    # Versuch 1: hermes send (kein Token nötig)
    import subprocess
    try:
        proc = subprocess.run(
            ["hermes", "send", "--to", "telegram", "--quiet", "-f", "-"],
            input=text, capture_output=True, text=True, timeout=30
        )
        if proc.returncode == 0:
            return True
    except (OSError, subprocess.TimeoutExpired):
        pass

    # Versuch 2: direkter API-Call (nur wenn Token verfügbar)
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status == 200
    except Exception:
        return False


# Batch: Sendet mehrere Findings als Panel
def send_panel(findings: list[dict]) -> bool:
    """Aggregiert mehrere Findings zu einem Notification-Panel."""
    if not findings:
        return False

    lines = ["📋 Hecate Panel", "─" * 20]
    for f in findings[:10]:
        emoji = RING_MAP.get(f.get("severity", "info"), ("⚪",))[0]
        lines.append(f"{emoji} {f.get('subject', 'Unbekannt')}: {f.get('evidence', '')[:60]}")
    if len(findings) > 10:
        lines.append(f"... und {len(findings) - 10} weitere")

    text = "\n".join(lines)
    import subprocess
    try:
        proc = subprocess.run(
            ["hermes", "send", "--to", "telegram", "--quiet", "-f", "-"],
            input=text, capture_output=True, text=True, timeout=30
        )
        return proc.returncode == 0
    except Exception:
        return False
