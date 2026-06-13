"""Proposal Verifier — zweiter Blick auf jeden Vorschlag.

Prueft Proposals vor der Freigabe auf:
1. Safety (Deny-List Treffer im Text)
2. Vollstaendigkeit (zwingende Abschnitte)
3. Konsistenz mit HECATE-Regeln (z.B. Ledger, Harness, 100x)
4. Keine Dopplung mit existierenden Proposals
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from safety.denylist import is_denied
from hecate.loop_factory import PROPOSALS_DIR

REQUIRED_SECTIONS = ("Zweck", "Implementierung", "Rollback")
HECATE_KEYWORDS = ("Ledger", "Harness", "reversibel", "safety.harness")


@dataclass(frozen=True)
class Verdict:
    ok: bool
    severity: str  # krit, hoch, info
    findings: list[str]


def _extract_sections(text: str) -> set[str]:
    """Findet alle Ueberschriften im Markdown."""
    return set(re.findall(r"^#{1,3}\s+(.+)$", text, re.MULTILINE))


def check_safety(text: str) -> list[str]:
    """Sucht Deny-List Treffer im Proposal-Text."""
    hits = []
    for line in text.splitlines():
        reason = is_denied(line)
        if reason:
            hits.append(f"Deny-List: {reason} in Zeile: {line.strip()[:80]}")
    return hits


def check_completeness(text: str) -> list[str]:
    """Prueft, ob wichtige Abschnitte vorhanden sind."""
    sections = _extract_sections(text)
    missing = [s for s in REQUIRED_SECTIONS if not any(s.lower() in sec.lower() for sec in sections)]
    return [f"Fehlt Abschnitt: {m}" for m in missing]


def check_hecate_alignment(text: str) -> list[str]:
    """Prueft, ob HECATE-Kernkonzepte beruehrt werden."""
    lower = text.lower()
    missing = []
    if not any(k.lower() in lower for k in HECATE_KEYWORDS):
        missing.append("Proposal erwaehnt weder Ledger noch Harness noch Reversibilitaet")
    return missing


def check_duplicate(title: str, proposals_dir: Path = PROPOSALS_DIR) -> list[str]:
    """Prueft auf offensichtliche Dopplung mit existierenden Proposals."""
    findings = []
    if not proposals_dir.exists():
        return findings
    title_words = set(re.findall(r"\w+", title.lower()))
    for p in proposals_dir.glob("*.md"):
        if p.name == title:
            continue
        other_words = set(re.findall(r"\w+", p.read_text(errors="ignore").lower()))
        overlap = len(title_words & other_words)
        if title_words and overlap / len(title_words) > 0.8:
            findings.append(f"Hohe Ueberschneidung mit existierendem Proposal: {p.name}")
    return findings


def verify_proposal(path: Path) -> Verdict:
    """Hauptfunktion: prueft ein Proposal und gibt Verdict zurueck."""
    text = path.read_text(errors="ignore")
    findings: list[str] = []
    findings.extend(check_safety(text))
    findings.extend(check_completeness(text))
    findings.extend(check_hecate_alignment(text))

    title = path.name
    for line in text.splitlines()[:20]:
        if line.startswith("# "):
            title = line[2:].strip()
            break
    findings.extend(check_duplicate(title))

    if any("Deny-List" in f for f in findings):
        return Verdict(ok=False, severity="krit", findings=findings)
    if any("Fehlt" in f for f in findings):
        return Verdict(ok=False, severity="hoch", findings=findings)
    if findings:
        return Verdict(ok=True, severity="info", findings=findings)
    return Verdict(ok=True, severity="info", findings=["Proposal sieht konsistent aus"])


def verify_all(proposals_dir: Path = PROPOSALS_DIR) -> dict:
    """Prueft alle existierenden Proposals."""
    if not proposals_dir.exists():
        return {"checked": 0, "failed": 0, "results": []}

    results = []
    failed = 0
    for p in sorted(proposals_dir.glob("*.md")):
        verdict = verify_proposal(p)
        if not verdict.ok:
            failed += 1
        results.append({
            "file": p.name,
            "ok": verdict.ok,
            "severity": verdict.severity,
            "findings": verdict.findings,
        })
    return {"checked": len(results), "failed": failed, "results": results}


def main() -> int:
    import json, sys
    if len(sys.argv) > 2 and sys.argv[1] == "check":
        path = Path(sys.argv[2])
        verdict = verify_proposal(path)
        print(json.dumps({
            "ok": verdict.ok,
            "severity": verdict.severity,
            "findings": verdict.findings,
        }, indent=2, ensure_ascii=False))
        return 0 if verdict.ok else 1

    summary = verify_all()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary["failed"]


if __name__ == "__main__":
    import sys
    sys.exit(main())
