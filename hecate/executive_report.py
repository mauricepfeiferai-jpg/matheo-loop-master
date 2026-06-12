#!/usr/bin/env python3
"""Executive Report — Loesungen statt Probleme.

Struktur:
1. Was ich schon gefixt habe (L2 autonom)
2. Was dein GO braucht (L3-L5)
3. Was neu ist — aber kein Stress
4. Dashboard + Actions

Filtert Info-Spam raus, gruppiert nach Handlbarkeit.
Ignoriert behobene/alte Scanner-Fehler.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

BUS = Path("/var/lib/loop-master/findings.jsonl")


def read_bus(n=100, hours=24):
    if not BUS.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out = []
    for line in open(BUS):
        if not line.strip():
            continue
        f = json.loads(line)
        # Skip alte Scanner-Fehler (behoben)
        if f.get("sensor") == "understand" and "scan-failed" in f.get("f_class", ""):
            continue
        try:
            ts = datetime.fromisoformat(f.get("ts", ""))
            if ts > cutoff:
                out.append(f)
        except Exception:
            pass
    return out[-n:]


def _has_suggested_fix(f):
    return bool(f.get("suggested_fix", "").strip())


def _is_new_today(f):
    try:
        ts = f.get("ts", "")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return today in ts
    except Exception:
        return False


def generate_executive_report():
    findings = read_bus(200, hours=24)

    auto_fixed = []
    needs_go = []
    needs_investigation = []

    for f in findings:
        sensor = f.get("sensor", "")
        if sensor in ("auto_remediate", "agent_team") and f.get("severity") == "info":
            auto_fixed.append(f)
        elif f.get("severity") in ("krit", "hoch"):
            if _has_suggested_fix(f):
                needs_go.append(f)
            else:
                needs_investigation.append(f)

    # Deduplizieren
    seen = set()
    unique_needs_go = []
    for f in needs_go:
        key = (f.get("f_class"), f.get("subject"))
        if key not in seen:
            seen.add(key)
            unique_needs_go.append(f)

    lines = ["Guten Morgen, Maurice", ""]

    # 1. Erledigt
    if auto_fixed:
        lines.append(f"Erledigt ({len(auto_fixed)}x)")
        for f in auto_fixed[-3:]:
            lines.append(f"  ✅ {f.get('subject', '—')[:40]}")
        lines.append("")
    else:
        lines.append("Erledigt — Alles stabil seit letztem Check.")
        lines.append("")

    # 2. Braucht GO
    if unique_needs_go:
        lines.append(f"Braucht dein GO ({len(unique_needs_go)} offen)")
        for f in unique_needs_go[:3]:
            icon = "🔴" if f["severity"] == "krit" else "🟠"
            subject = f.get("subject", "—")[:45]
            fix = f.get("suggested_fix", "")[:60]
            lines.append(f"  {icon} {subject}")
            if fix:
                lines.append(f"     → Fix: {fix}")
        if len(unique_needs_go) > 3:
            lines.append(f"  ... und {len(unique_needs_go) - 3} weitere.")
        lines.append("")

    # 3. Neu unklar
    new_investigation = [f for f in needs_investigation if _is_new_today(f)]
    if new_investigation:
        lines.append(f"Neu — unklar ({len(new_investigation)}x)")
        for f in new_investigation[:2]:
            lines.append(f"  🟠 {f.get('subject', '—')[:45]}")
        lines.append("")

    # 4. Status
    krit = sum(1 for f in findings if f.get("severity") == "krit")
    hoch = sum(1 for f in findings if f.get("severity") == "hoch")
    lines.append(f"Status: {krit} 🔴 | {hoch} 🟠 | Dashboard: http://localhost:8877")
    lines.append("")
    lines.append("Befehle: /status /sensors /findings /dashboard /help")

    return "\n".join(lines)


def generate_quick_status():
    findings = read_bus(50, hours=24)
    krit = sum(1 for f in findings if f.get("severity") == "krit")
    hoch = sum(1 for f in findings if f.get("severity") == "hoch")

    if krit == 0 and hoch == 0:
        return "Alles gruen. Keine kritischen oder hohen Findings."

    action_items = [f for f in findings if f.get("severity") in ("krit", "hoch") and f.get("suggested_fix")]
    if action_items:
        top = action_items[0]
        return (
            f"{krit} 🔴 / {hoch} 🟠 offen\n\n"
            f"Wichtigstes: {top.get('subject', '—')[:40]}\n"
            f"→ {top.get('suggested_fix', 'Fix unbekannt')[:60]}\n\n"
            f"Soll ich das fixen?"
        )
    return f"{krit} 🔴 / {hoch} 🟠 offen — aber keine bekannten Fixes dabei."


if __name__ == "__main__":
    print(generate_executive_report())
