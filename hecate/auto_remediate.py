#!/usr/bin/env python3
"""Auto-Remediation — Bekannte Probleme automatisch fixen (L2).

Wenn ein Problem bekannt ist UND ein Fix im Ledger existiert,
wende Fix automatisch an.
"""
import json, subprocess
from datetime import datetime, timezone
from pathlib import Path

BUS = Path("/var/lib/loop-master/findings.jsonl")
LEDGER = Path("/var/lib/loop-master/ledger.jsonl")

def known_fixes() -> dict:
    """Lade bekannte Fixes aus Ledger."""
    fixes = {}
    if not LEDGER.exists(): return fixes
    for line in open(LEDGER):
        if line.strip():
            e = json.loads(line)
            # Suche nach erfolgreichen Fixes
            if "fix" in e.get("phase","").lower() and e.get("status") == "ok":
                fixes[e.get("loop","")] = e.get("output_path","")
    return fixes

def auto_remediate():
    fixes = known_fixes()
    if not BUS.exists(): return 0
    remediated = 0
    for line in open(BUS):
        if not line.strip(): continue
        f = json.loads(line)
        if f.get("severity") not in ("krit","hoch"): continue
        f_class = f.get("f_class","")
        # Check if fix known
        for loop, fix_path in fixes.items():
            if loop in f_class:
                # Auto-remediate
                print(f"Auto-Remediation: {f_class} → applying {fix_path}")
                try:
                    # Run fix script
                    r = subprocess.run(["bash", fix_path], capture_output=True, text=True, timeout=30)
                    if r.returncode == 0:
                        remediated += 1
                        # Emit success
                        success = {
                            "sensor": "auto_remediate",
                            "severity": "info",
                            "f_class": f"auto_remediate.applied",
                            "subject": f"Auto-fix applied for {f_class}",
                            "evidence": f"Fix: {fix_path}",
                            "ts": datetime.now(timezone.utc).isoformat(),
                        }
                        with open(BUS, "a") as x:
                            x.write(json.dumps(success, ensure_ascii=False) + "\n")
                except Exception as e:
                    print(f"Auto-Remediation failed: {e}")
    return remediated

if __name__ == "__main__":
    n = auto_remediate()
    print(f"Auto-Remediation: {n} fixes applied")
