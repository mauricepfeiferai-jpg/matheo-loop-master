"""Hermes Adapter Health-Check — prüft, dass Hermes Agent erreichbar ist.

Wird vom Proposal `hermes-agent-integration` verwendet, sobald freigegeben.
"""
import traceback
from datetime import datetime, timezone

from hecate.hermes_adapter import status
from sensors.bus import Finding, emit


def _build_finding(ok: bool, evidence: str) -> Finding:
    return Finding(
        sensor="hermes_adapter",
        severity="info" if ok else "hoch",
        f_class="hermes.status_ok" if ok else "hermes.status_failed",
        subject="Hermes Agent Status",
        evidence=evidence[:200],
        suggested_fix="" if ok else "Hermes CLI/Netz prüfen; `hermes doctor` ausführen",
        ts=datetime.now(timezone.utc).isoformat(),
    )


def main() -> int:
    try:
        r = status()
        evidence = (r.stdout[:200] if r.ok else (r.stderr[:200] or f"exit {r.returncode}")) or "no output"
        finding = _build_finding(r.ok, evidence)
        returncode = 0 if r.ok else 1
    except Exception as exc:
        finding = _build_finding(False, f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[:200]}")
        returncode = 1

    emit([finding])
    print(f"Hermes status: {'ok' if finding.f_class == 'hermes.status_ok' else 'failed'}")
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
