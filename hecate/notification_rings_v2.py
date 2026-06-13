#!/usr/bin/env python3
"""Notification Rings v2 — Enhanced Telegram mit Keyboards.

In Proposal-only-Modus werden Panels/Alerts NICHT mehr an Telegram
verschickt, sondern in den Tagesreport geschrieben. Telegram bleibt
fuer echte Entscheidungs-Proposals reserviert.
"""
from datetime import datetime, timezone
from pathlib import Path

RING_MAP = {
    "krit": ("🔴", "KRITISCH", "sofort"),
    "hoch": ("🟠", "HOCH", "1h"),
    "mittel": ("🟡", "MITTEL", "4h"),
    "info": ("🔵", "INFO", "24h"),
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


def send_panel(findings, with_keyboard=True):
    by_sev = {"krit": [], "hoch": [], "mittel": [], "info": []}
    for f in findings:
        sev = f.get("severity", "info")
        if sev in by_sev:
            by_sev[sev].append(f)
    lines = ["*🌑 HECATE Panel*\n"]
    for sev in ["krit", "hoch", "mittel", "info"]:
        items = by_sev[sev]
        if items:
            icon, label, sla = RING_MAP[sev]
            lines.append(f"\n{icon} *{label}* (SLA: {sla})\n")
            for f in items[:5]:
                subject = f.get("subject", "—")[:40].replace("_", " ")
                lines.append(f"• `{f.get('sensor','?')}` {subject}\n")
    return _append_to_report("\n".join(lines))


def send_alert(finding):
    icon, label, sla = RING_MAP.get(finding.get("severity", "info"), ("🔵", "INFO", "24h"))
    text = (
        f"{icon} *{label}* (SLA: {sla})\n\n"
        f"`{finding.get('sensor','?')}`\n"
        f"{finding.get('subject','—').replace('_', ' ')}\n\n"
        f"_{finding.get('evidence','')[:100].replace('_', ' ')}_"
    )
    return _append_to_report(text)
