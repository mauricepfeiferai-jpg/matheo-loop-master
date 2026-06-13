"""Notification-Rings — Priorisierte Alerts aus Hecate.

In Proposal-only-Modus werden Routine-Alerts NICHT mehr an Telegram
geschickt, sondern an den Tagesreport angehaengt. Telegram erhaelt nur
noch echte Entscheidungs-Proposals.
"""
import os
from datetime import datetime, timezone
from pathlib import Path

# Prioritäts-Ring-Map (cmux-Konzept: blauer Ring = Aufmerksamkeit)
RING_MAP = {
    "krit":   ("🔴", "KRITISCH", "sofort"),
    "hoch":   ("🟠", "HOCH",     "1h"),
    "mittel": ("🟡", "MITTEL",   "4h"),
    "info":   ("🔵", "INFO",     "24h"),
    "ok":     ("🟢", "OK",       "—"),
}


def _report_path() -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Path(f"/var/lib/loop-master/daily_report_{today}.md")


def _append_to_report(text: str) -> bool:
    path = _report_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n\n")
        return True
    except Exception:
        return False


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
    """Schreibt einen Ring in den Tagesreport (kein Telegram-Spam)."""
    text = format_ring(level, subject, evidence, suggested_fix)
    return _append_to_report(text)


def send_panel(findings: list[dict]) -> bool:
    """Aggregiert mehrere Findings zu einem Panel im Tagesreport."""
    if not findings:
        return False

    lines = ["📋 Hecate Panel", "─" * 20]
    for f in findings[:10]:
        emoji = RING_MAP.get(f.get("severity", "info"), ("⚪",))[0]
        lines.append(f"{emoji} {f.get('subject', 'Unbekannt')}: {f.get('evidence', '')[:60]}")
    if len(findings) > 10:
        lines.append(f"... und {len(findings) - 10} weitere")

    return _append_to_report("\n".join(lines))
