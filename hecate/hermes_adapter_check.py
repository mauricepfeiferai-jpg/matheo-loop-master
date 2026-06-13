"""Hermes Adapter Health-Check — prüft, dass Hermes Agent erreichbar ist.

Wird vom Proposal `hermes-agent-integration` verwendet, sobald freigegeben.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from hecate.hermes_adapter import status

BUS = Path("/var/lib/loop-master/findings.jsonl")


def main() -> int:
    r = status()
    finding = {
        "sensor": "hermes_adapter",
        "severity": "info" if r.ok else "hoch",
        "f_class": "hermes.status_ok" if r.ok else "hermes.status_failed",
        "subject": "Hermes Agent Status",
        "evidence": (r.stdout[:200] if r.ok else (r.stderr[:200] or f"exit {r.returncode}")) or "no output",
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with BUS.open("a") as f:
        f.write(json.dumps(finding, ensure_ascii=False) + "\n")
    print(f"Hermes status: {'ok' if r.ok else 'failed'} (exit {r.returncode})")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
