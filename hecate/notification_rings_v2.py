#!/usr/bin/env python3
"""Notification Rings v2 — Enhanced Telegram mit Keyboards.

4 Prioritäts-Ringe: 🔴🟠🟡🔵
Enhanced: Keyboards, MarkdownV2, Screenshots.
"""
from hecate.telegram_enhanced import send_message, send_photo, format_findings, ack_keyboard
from pathlib import Path
from datetime import datetime, timezone

RING_MAP = {
    "krit": ("🔴", "KRITISCH", "sofort"),
    "hoch": ("🟠", "HOCH", "1h"),
    "mittel": ("🟡", "MITTEL", "4h"),
    "info": ("🔵", "INFO", "24h"),
}

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
            lines.append(f"\n{icon} *{label}* \\(SLA: {sla}\\)\n")
            for f in items[:5]:
                subject = f.get("subject", "—")[:40].replace("_", "\\_")
                lines.append(f"• `{f.get('sensor','?')}` {subject}\n")
    text = "\n".join(lines)
    kb = None
    if with_keyboard and (by_sev["krit"] or by_sev["hoch"]):
        first = (by_sev["krit"] + by_sev["hoch"])[0]
        kb = ack_keyboard(first.get("subject", ""))
    return send_message(text, keyboard=kb)

def send_alert(finding):
    icon, label, sla = RING_MAP.get(finding.get("severity", "info"), ("🔵", "INFO", "24h"))
    text = (
        f"{icon} *{label}* \\(SLA: {sla}\\)\n\n"
        f"`{finding.get('sensor','?')}`\n"
        f"{finding.get('subject','—').replace('_', '\\_')}\n\n"
        f"_{finding.get('evidence','')[:100].replace('_', '\\_')}_"
    )
    kb = ack_keyboard(finding.get("subject", ""))
    return send_message(text, keyboard=kb)
