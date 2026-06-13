#!/usr/bin/env python3
"""Auto-Remediation — DEAKTIVIERT.

Das System befindet sich im Proposal-only-Modus. Automatische Fixes werden
NICHT ausgefuehrt. Stattdessen wird ein Audit-Eintrag geschrieben und die
Verantwortung an den Menschen delegiert.
"""
from datetime import datetime, timezone
from pathlib import Path

from sensors.bus import Finding, emit

BUS = Path("/var/lib/loop-master/findings.jsonl")
LEDGER = Path("/var/lib/loop-master/ledger.jsonl")


def known_fixes() -> dict:
    """Lade bekannte Fixes aus Ledger (weiterhin fuer Reports verwendet)."""
    fixes = {}
    if not LEDGER.exists():
        return fixes
    for line in open(LEDGER):
        if line.strip():
            e = __import__("json").loads(line)
            if "fix" in e.get("phase", "").lower() and e.get("status") == "ok":
                fixes[e.get("loop", "")] = e.get("output_path", "")
    return fixes


def auto_remediate() -> int:
    """Proposal-only: fuehrt keine Aktion aus, nur Audit-Eintrag."""
    fixes = known_fixes()
    finding = Finding(
        sensor="auto_remediate",
        severity="info",
        f_class="auto_remediate.proposal_only",
        subject="Auto-Remediation deaktiviert",
        evidence=(
            f"{len(fixes)} bekannte Fixes im Ledger, "
            "keine automatische Ausfuehrung. Warte auf Maurice-GO."
        ),
        suggested_fix="Proposal pruefen und manuell freigeben (/approve <proposal>)",
        ts=datetime.now(timezone.utc).isoformat(),
    )
    emit([finding])
    return 0


if __name__ == "__main__":
    n = auto_remediate()
    print(f"Auto-Remediation: {n} fixes applied (proposal-only mode)")
