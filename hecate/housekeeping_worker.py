#!/usr/bin/env python3
"""Housekeeping Worker — führt freigegebene Aufräum-Aktionen aus und verifiziert.

Ablauf:
  1. approved Proposals aus /root/projects/loop-master/proposals laden
  2. Aktion ausführen (archive/delete/docker_prune) mit Backup bei archive
  3. Ledger-Eintrag schreiben
  4. Verify-Loop prüft Erfolg
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from hecate.ledger import Ledger
from hecate.system_housekeeper import CANDIDATES_PATH, Candidate

ARCHIVE_DIR = Path("/root/_archive")
PROPOSALS_DIR = Path("/root/projects/loop-master/proposals")
LEDGER = Ledger()


def _candidate_by_path(target: str) -> Candidate | None:
    if not CANDIDATES_PATH.exists():
        return None
    for line in open(CANDIDATES_PATH):
        if not line.strip():
            continue
        data = json.loads(line)
        if data["path"] == target or Path(data["path"]).name == target:
            return Candidate(**data)
    return None


def _run(cmd: list[str], timeout: int = 300) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr)[:500]
    except Exception as exc:
        return False, str(exc)[:500]


def action_archive(c: Candidate) -> tuple[bool, str]:
    src = Path(c.path)
    if not src.exists():
        return False, f"source missing: {c.path}"
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    dest = ARCHIVE_DIR / f"{src.name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    try:
        if src.is_dir():
            shutil.move(str(src), str(dest))
        else:
            shutil.move(str(src), str(dest))
        return True, f"archived to {dest}"
    except Exception as exc:
        return False, str(exc)


def action_delete(c: Candidate) -> tuple[bool, str]:
    target = Path(c.path)
    if not target.exists():
        return False, f"target missing: {c.path}"
    try:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return True, f"deleted {c.path}"
    except Exception as exc:
        return False, str(exc)


def action_docker_prune(c: Candidate) -> tuple[bool, str]:
    # Nur dangling images, stopped containers, unused networks, unlabeled volumes
    ok, out = _run(["docker", "system", "prune", "-f", "--volumes"], timeout=300)
    return ok, out[:200]


def action_truncate_log(c: Candidate) -> tuple[bool, str]:
    target = Path(c.path)
    if not target.exists():
        return False, f"log missing: {c.path}"
    try:
        # Rotiere: backup .old und leere Datei
        backup = target.with_suffix(target.suffix + ".old")
        shutil.copy2(target, backup)
        target.write_text("")
        return True, f"truncated {c.path} (backup {backup})"
    except Exception as exc:
        return False, str(exc)


ACTIONS: dict[str, Callable[[Candidate], tuple[bool, str]]] = {
    "archive_to_backup": action_archive,
    "delete": action_delete,
    "docker_prune": action_docker_prune,
    "truncate_log": action_truncate_log,
}


def execute_candidate(c: Candidate, dry_run: bool = False) -> dict:
    if c.action not in ACTIONS:
        return {"ok": False, "error": f"unknown action: {c.action}"}

    rid = LEDGER.start(c.action, note=json.dumps({"path": c.path, "size_bytes": c.size_bytes}))

    output_dir = Path("/var/lib/loop-master/housekeeping")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{c.action}-{Path(c.path).name}-{rid}.json"

    if dry_run:
        output_path.write_text(json.dumps({"dry_run": True, "path": c.path}, ensure_ascii=False))
        LEDGER.finish(rid, output_path=str(output_path), note=f"would {c.action} {c.path}")
        return {"ok": True, "dry_run": True, "rid": rid}

    ok, note = ACTIONS[c.action](c)
    result = {"ok": ok, "path": c.path, "action": c.action, "note": note}
    output_path.write_text(json.dumps(result, ensure_ascii=False))
    status = "failed" if not ok else None
    LEDGER.finish(rid, status=status, output_path=str(output_path))
    return {"ok": ok, "rid": rid, "note": note, "output_path": str(output_path)}


def verify_candidate(c: Candidate) -> dict:
    target = Path(c.path)
    if c.action in ("delete", "archive_to_backup"):
        exists = target.exists()
        ok = not exists if c.action == "delete" else (not exists or target.stat().st_size == 0)
        return {"ok": ok, "exists": exists, "note": "verify post-action"}
    if c.action == "docker_prune":
        ok, out = _run(["docker", "system", "df"], timeout=30)
        return {"ok": ok, "note": out[:200]}
    if c.action == "truncate_log":
        if target.exists():
            return {"ok": target.stat().st_size < 1024**2, "size": target.stat().st_size}
        return {"ok": False, "note": "log missing"}
    return {"ok": False, "note": "no verifier"}


def _proposal_status(proposal_id: str) -> str:
    path = PROPOSALS_DIR / f"{proposal_id}.md"
    if not path.exists():
        return "missing"
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'status:\s*(\w+)', text)
    return m.group(1) if m else "vorgeschlagen"


def _candidate_from_proposal(proposal_id: str) -> Candidate | None:
    """Extrahiert Pfad aus housekeeping Proposal-Text und findet Candidate."""
    path = PROPOSALS_DIR / f"{proposal_id}.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'Aktion\s*\n[^\n]*\n([^\n]+)', text)
    if not m:
        return None
    action_line = m.group(1).strip()
    # Format: "archive_to_backup auf /root/gpe-openclaw"
    if " auf " in action_line:
        target = action_line.split(" auf ")[-1].strip()
    else:
        target = action_line.split()[-1].strip()
    return _candidate_by_path(target)


def process_approved_proposals(dry_run: bool = False) -> list[dict]:
    """Fuehrt alle approved housekeeping Proposals aus."""
    results = []
    for p in PROPOSALS_DIR.glob("housekeep-*.md"):
        status = _proposal_status(p.stem)
        if status != "approved":
            continue
        c = _candidate_from_proposal(p.stem)
        if not c:
            results.append({"proposal": p.stem, "ok": False, "error": "candidate not found"})
            continue
        exec_result = execute_candidate(c, dry_run=dry_run)
        if exec_result.get("ok"):
            verify_result = verify_candidate(c)
            results.append({"proposal": p.stem, "executed": exec_result, "verified": verify_result})
            # Setze Status auf umgesetzt, wenn Verify ok
            if verify_result.get("ok") and not dry_run:
                _set_proposal_status(p.stem, "verifiziert")
        else:
            results.append({"proposal": p.stem, "executed": exec_result, "verified": {"ok": False}})
    return results


def _set_proposal_status(proposal_id: str, status: str) -> None:
    path = PROPOSALS_DIR / f"{proposal_id}.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    new_text = re.sub(r'status:\s*\w+', f'status: {status}', text)
    path.write_text(new_text, encoding="utf-8")


def process_approved(approved_paths: list[str], dry_run: bool = False) -> list[dict]:
    """Legacy API: erwartet Pfad-Liste."""
    results = []
    for name in approved_paths:
        target = Path(name).name
        c = _candidate_by_path(target)
        if not c:
            results.append({"target": target, "ok": False, "error": "candidate not found"})
            continue
        if c.risk_class not in ("safe_delete", "safe_archive"):
            results.append({"target": target, "ok": False, "error": f"not approved for auto-execution: {c.risk_class}"})
            continue
        exec_result = execute_candidate(c, dry_run=dry_run)
        if exec_result.get("ok"):
            verify_result = verify_candidate(c)
            results.append({"target": target, "executed": exec_result, "verified": verify_result})
        else:
            results.append({"target": target, "executed": exec_result, "verified": {"ok": False}})
    return results


if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv
    if "--apply-approved" in sys.argv:
        results = process_approved_proposals(dry_run=dry)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        sys.exit(0)

    # Demo: führe safe-Aktionen aus dem candidates.jsonl aus
    if not CANDIDATES_PATH.exists():
        print("no candidates")
        sys.exit(1)
    approved = []
    for line in open(CANDIDATES_PATH):
        if not line.strip():
            continue
        c = Candidate(**json.loads(line))
        if c.risk_class in ("safe_delete", "safe_archive"):
            approved.append(c.path)
    results = process_approved(approved, dry_run=dry)
    print(json.dumps(results, indent=2, ensure_ascii=False))
