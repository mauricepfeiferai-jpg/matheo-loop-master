#!/usr/bin/env python3
"""Escalation Router — Proposal-only Telegram-Ausgabe.

- Findings werden in /var/log/loop-master/escalation.jsonl geloggt.
- Telegram wird nur noch fuer echte Entscheidungs-Proposals verwendet
  (f_class in TELEGRAM_F_CLASSES) oder vom Proposal-Bot gesteuert.
- Alle anderen Alerts (krit/hoch) landen im Report, nicht im Chat.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from hecate.hermes_adapter import send_message
from hecate.rate_limiter import can_send_telegram, telegram_wait

BUS = Path("/var/lib/loop-master/findings.jsonl")

# Nur diese Finding-Typen duerfen direkt an Telegram gehen.
# Alles andere wird nur noch geloggt.
TELEGRAM_F_CLASSES = {"proposal", "governance"}

# Weiterhin Telegram-faehig, aber vom Proposal-Bot verwaltet.
SEVERITY_MAP = {
    "krit": ["log"],
    "hoch": ["log"],
    "mittel": ["log"],
    "info": ["log"],
}


def _is_telegram_finding(finding: dict) -> bool:
    f_class = finding.get("f_class", "")
    return any(f_class.startswith(prefix + ".") for prefix in TELEGRAM_F_CLASSES)


def route_finding(finding: dict) -> list:
    """Bestimmt Zielkanäle fuer ein Finding."""
    sev = finding.get("severity", "info")
    channels = SEVERITY_MAP.get(sev, ["log"])
    results = []
    for ch in channels:
        if ch == "telegram" and _is_telegram_finding(finding):
            results.append(_send_telegram(finding))
        elif ch == "log":
            results.append(_send_log(finding))
    return results


def _send_telegram(finding: dict) -> dict:
    """Sendet via Hermes Adapter NUR fuer Proposal/Governance-Findings."""
    icon = {"krit": "🔴", "hoch": "🟠", "mittel": "🟡", "info": "🔵"}.get(finding["severity"], "⚪")
    msg = f"{icon} [{finding.get('sensor', '?')}] {finding.get('subject', '—')}\n{finding.get('evidence', '')[:200]}"
    if not can_send_telegram():
        wait = telegram_wait()
        _send_log({**finding, "_throttled": True,
                   "_note": f"Telegram rate-limit aktiv; wartet {wait:.0f}s"})
        return {"channel": "telegram", "ok": False, "error": f"rate-limited: wait {wait:.0f}s"}
    try:
        r = send_message("telegram", msg, quiet=True)
        return {"channel": "telegram", "ok": r.ok, "output": r.stdout[:100]}
    except Exception as e:
        return {"channel": "telegram", "ok": False, "error": str(e)}


def _send_log(finding: dict) -> dict:
    """Schreibt in dediziertes Escalation-Log."""
    log_path = Path("/var/log/loop-master/escalation.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "finding": finding,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"channel": "log", "ok": True}


def process_bus(limit: int = 10) -> list:
    """Verarbeitet letzte n Findings aus dem Bus."""
    if not BUS.exists():
        return []
    findings = []
    with open(BUS) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                findings.append(json.loads(line))
            except json.JSONDecodeError as exc:
                _send_log({"sensor": "escalation", "severity": "hoch",
                           "subject": "Bus JSON decode error", "evidence": str(exc)[:120]})
    results = []
    for f in findings[-limit:]:
        if f.get("severity") in ("krit", "hoch") or _is_telegram_finding(f):
            results.extend(route_finding(f))
    return results


if __name__ == "__main__":
    results = process_bus()
    for r in results:
        print(f"{r['channel']}: {'OK' if r['ok'] else 'FAIL'}")
