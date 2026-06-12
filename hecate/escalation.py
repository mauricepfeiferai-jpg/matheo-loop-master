#!/usr/bin/env python3
"""Escalation Router — verteilt Alerts auf Kanäle nach Severity.

Schließt Lücke #16: Kein Escalation-Routing.
"""
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BUS = Path("/var/lib/loop-master/findings.jsonl")

SEVERITY_MAP = {
    "krit": ["telegram", "log"],
    "hoch": ["telegram", "log"],
    "mittel": ["log"],
    "info": ["log"],
}


def route_finding(finding: dict) -> list:
    """Bestimmt Zielkanäle für ein Finding."""
    sev = finding.get("severity", "info")
    channels = SEVERITY_MAP.get(sev, ["log"])
    results = []
    for ch in channels:
        if ch == "telegram":
            results.append(_send_telegram(finding))
        elif ch == "log":
            results.append(_send_log(finding))
    return results


def _send_telegram(finding: dict) -> dict:
    """Sendet via hermes CLI."""
    icon = {"krit": "🔴", "hoch": "🟠", "mittel": "🟡", "info": "🔵"}.get(finding["severity"], "⚪")
    msg = f"{icon} [{finding.get('sensor', '?')}] {finding.get('subject', '—')}\n{finding.get('evidence', '')[:200]}"
    try:
        r = subprocess.run(
            ["hermes", "send", "--to", "telegram", "-q", msg],
            capture_output=True, text=True, timeout=30
        )
        return {"channel": "telegram", "ok": r.returncode == 0, "output": r.stdout[:100]}
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
            if line.strip():
                findings.append(json.loads(line))
    results = []
    for f in findings[-limit:]:
        if f.get("severity") in ("krit", "hoch"):
            results.extend(route_finding(f))
    return results


if __name__ == "__main__":
    results = process_bus()
    for r in results:
        print(f"{r['channel']}: {'OK' if r['ok'] else 'FAIL'}")
