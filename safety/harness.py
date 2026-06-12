"""Transaktionale Ausfuehrung einer Aktion mit Checkpoint + Auto-Rollback.
Jede autonome Auto-Fix-Aktion des Executive Loop MUSS hierdurch laufen."""
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from safety.denylist import is_denied


@dataclass
class SafeAction:
    id: str
    do_cmd: str
    undo_cmd: str            # Fallback-Undo falls Snapshot nicht greift
    verify_cmd: str          # exit 0 == gesund
    snapshot_files: list[str] = field(default_factory=list)
    audit_path: str = "/var/log/loop-master/audit.jsonl"


@dataclass
class Result:
    ok: bool
    rolled_back: bool = False
    denied: str | None = None
    detail: str = ""


def _run(cmd: str) -> int:
    return subprocess.run(cmd, shell=True, capture_output=True).returncode


def _audit(action: "SafeAction", outcome: str, detail: str = "") -> None:
    p = Path(action.audit_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": datetime.now().isoformat(), "id": action.id,
             "outcome": outcome, "cmd": action.do_cmd, "detail": detail}
    with p.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def _restore(saved: list[tuple[str, str]], action: "SafeAction") -> None:
    for src, dst in saved:
        shutil.copy2(dst, src)
    if not saved:
        _run(action.undo_cmd)


def run(action: "SafeAction") -> "Result":
    reason = is_denied(action.do_cmd)
    if reason:
        _audit(action, "denied", reason)
        return Result(ok=False, denied=reason, detail=reason)

    # Checkpoint: Dateien sichern
    ckpt = Path(f"/tmp/loop-master-ckpt/{action.id}")
    ckpt.mkdir(parents=True, exist_ok=True)
    saved: list[tuple[str, str]] = []
    for src in action.snapshot_files:
        if Path(src).exists():
            dst = ckpt / Path(src).name
            shutil.copy2(src, dst)
            saved.append((src, str(dst)))

    # Do
    if _run(action.do_cmd) != 0:
        _restore(saved, action)
        _audit(action, "do_failed_rolled_back")
        return Result(ok=False, rolled_back=True, detail="do_cmd exit != 0")

    # Verify
    if _run(action.verify_cmd) != 0:
        _restore(saved, action)
        _audit(action, "verify_failed_rolled_back")
        return Result(ok=False, rolled_back=True, detail="verify failed")

    _audit(action, "success")
    return Result(ok=True)
