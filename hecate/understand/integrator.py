#!/usr/bin/env python3
"""Understand Integrator — Scanner + Analyzer regelmäßig laufen, Ergebnisse in Bus.

Schließt Lücke #4: Understand-System ist isoliert.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

BUS = Path("/var/lib/loop-master/findings.jsonl")
PROJECTS = ["/root/projects/content-engine", "/root/projects/loop-master"]

def run_inventory():
    """Scannt alle Projekte, schreibt Ergebnisse in Bus."""
    import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent)); from understand.scanner import scan_project
    for proj in PROJECTS:
        try:
            data = scan_project(proj)
            finding = {
                "sensor": "understand",
                "severity": "info",
                "f_class": "understand.inventory",
                "subject": f"Inventory {Path(proj).name}",
                "evidence": f"{data.get('totalFiles',0)} files, languages: {list(data.get('languages',{}).keys())}",
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            with open(BUS, "a") as f:
                f.write(json.dumps(finding, ensure_ascii=False) + "\n")
        except Exception as e:
            finding = {
                "sensor": "understand",
                "severity": "hoch",
                "f_class": "understand.scan-failed",
                "subject": f"Scan failed {Path(proj).name}",
                "evidence": str(e)[:200],
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            with open(BUS, "a") as f:
                f.write(json.dumps(finding, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    run_inventory()
    print("Inventory scan complete")
