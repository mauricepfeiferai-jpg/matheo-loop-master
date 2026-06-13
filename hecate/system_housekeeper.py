#!/usr/bin/env python3
"""System Housekeeper — Scannt Server, klassifiziert Aufräum-Kandidaten, schlägt Aktionen vor.

Ablauf:
  1. scan() -> candidates.jsonl
  2. classify() -> risk_class: safe_delete / safe_archive / migrate_review / ask_maurice
  3. propose() -> Proposal + optional Telegram-Freigabe bei ask_maurice
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from hecate.loop_factory import create_proposal
from hecate.reasoning_router import ReasoningRouter, TaskType

REPORT_DIR = Path("/var/lib/loop-master/housekeeping")
CANDIDATES_PATH = REPORT_DIR / "candidates.jsonl"


@dataclass
class Candidate:
    path: str
    size_bytes: int
    age_days: float
    category: str
    reason: str
    risk_class: str = "unclassified"
    action: str = "pending"
    confidence: float = 0.0
    evidence: str = ""


def _run(cmd: list[str], timeout: int = 60) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception as exc:
        return f"ERROR: {exc}"


def _file_age_days(p: Path) -> float:
    try:
        return (time.time() - p.stat().st_mtime) / 86400.0
    except Exception:
        return 0.0


def scan_large_dirs(min_size_gb: float = 1.0) -> list[Candidate]:
    """Top-Level-Verzeichnisse unter /root, /opt, /tmp, /var, /home."""
    bases = [Path("/root"), Path("/opt"), Path("/tmp"), Path("/var"), Path("/home")]
    min_bytes = int(min_size_gb * 1024**3)
    out: list[Candidate] = []
    for base in bases:
        if not base.exists():
            continue
        for p in base.iterdir():
            try:
                if p.is_dir() and not p.is_symlink():
                    size = _dir_size(p)
                    if size >= min_bytes:
                        out.append(Candidate(
                            path=str(p),
                            size_bytes=size,
                            age_days=_file_age_days(p),
                            category="large_dir",
                            reason=f"Directory >= {min_size_gb} GB",
                        ))
                elif p.is_file() and not p.is_symlink() and p.stat().st_size >= min_bytes:
                    out.append(Candidate(
                        path=str(p),
                        size_bytes=p.stat().st_size,
                        age_days=_file_age_days(p),
                        category="large_file",
                        reason=f"File >= {min_size_gb} GB",
                    ))
            except PermissionError:
                continue
    return sorted(out, key=lambda x: x.size_bytes, reverse=True)


def _dir_size(p: Path) -> int:
    total = 0
    try:
        for entry in os.scandir(p):
            if entry.is_dir(follow_symlinks=False):
                total += _dir_size(Path(entry.path))
            else:
                total += entry.stat(follow_symlinks=False).st_size
    except PermissionError:
        pass
    return total


def scan_logs(max_size_mb: float = 50.0) -> list[Candidate]:
    min_bytes = int(max_size_mb * 1024**2)
    out: list[Candidate] = []
    for p in Path("/var/log").rglob("*"):
        try:
            if p.is_file() and not p.is_symlink() and p.stat().st_size >= min_bytes:
                out.append(Candidate(
                    path=str(p),
                    size_bytes=p.stat().st_size,
                    age_days=_file_age_days(p),
                    category="log",
                    reason=f"Log file >= {max_size_mb} MB",
                ))
        except PermissionError:
            continue
    return sorted(out, key=lambda x: x.size_bytes, reverse=True)[:20]


def scan_docker_reclaimable() -> list[Candidate]:
    out: list[Candidate] = []
    df = _run(["docker", "system", "df", "--format", "{{json .}}"], timeout=30)
    for line in df.strip().splitlines():
        try:
            item = json.loads(line)
            typ = item.get("Type", "")
            reclaim = item.get("ReclaimableSize", "0")
            if typ and "GB" in reclaim:
                out.append(Candidate(
                    path=f"docker:{typ}",
                    size_bytes=_parse_size(reclaim),
                    age_days=0.0,
                    category="docker",
                    reason=f"Docker {typ} reclaimable {reclaim}",
                ))
        except Exception:
            continue
    return out


def _parse_size(s: str) -> int:
    s = s.strip().replace(",", "")
    mult = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    for unit, m in mult.items():
        if s.endswith(unit):
            return int(float(s[:-len(unit)].strip()) * m)
    return 0


def scan_old_backups(archive_base: Path = Path("/root/_backups"), max_age_days: float = 3.0) -> list[Candidate]:
    out: list[Candidate] = []
    if not archive_base.exists():
        return out
    for p in archive_base.iterdir():
        age = _file_age_days(p)
        if age > max_age_days:
            size = _dir_size(p) if p.is_dir() else p.stat().st_size
            out.append(Candidate(
                path=str(p),
                size_bytes=size,
                age_days=age,
                category="old_backup",
                reason=f"Backup older than {max_age_days} days",
            ))
    return sorted(out, key=lambda x: x.size_bytes, reverse=True)


def _is_active_project(name: str) -> bool:
    """Prueft, ob ein systemd-Service mit dem Namen laeuft/gerade startet."""
    try:
        r = subprocess.run(
            ["systemctl", "is-active", f"{name}.service"],
            capture_output=True, text=True, timeout=5,
        )
        state = r.stdout.strip().lower()
        return state in ("active", "activating")
    except Exception:
        return False


def scan_deprecated_dirs() -> list[Candidate]:
    markers = [
        "/opt/_DEPRECATED_",
        "/root/_archive",
        "/root/gpe-openclaw",
        "/root/openclaw",
        "/root/codex_backup_",
        "/root/legal_mac_pull_",
    ]
    out: list[Candidate] = []
    for marker in markers:
        base = Path(marker.rstrip("_"))
        if not base.exists():
            continue
        for p in base.parent.glob(base.name + "*"):
            if p.exists() and p.name != "loop-master":
                size = _dir_size(p) if p.is_dir() else p.stat().st_size
                out.append(Candidate(
                    path=str(p),
                    size_bytes=size,
                    age_days=_file_age_days(p),
                    category="deprecated",
                    reason="Name/location marks deprecated project",
                ))
    return out


def scan_all() -> list[Candidate]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    all_candidates = []
    all_candidates.extend(scan_large_dirs(min_size_gb=1.0))
    all_candidates.extend(scan_logs(max_size_mb=50.0))
    all_candidates.extend(scan_docker_reclaimable())
    all_candidates.extend(scan_old_backups(max_age_days=3.0))
    all_candidates.extend(scan_deprecated_dirs())
    with open(CANDIDATES_PATH, "w", encoding="utf-8") as f:
        for c in all_candidates:
            f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")
    return all_candidates


def classify_candidate(router: ReasoningRouter | None, c: Candidate) -> Candidate:
    """Deterministische Risiko-Klassifikation + optionale LLM-Überprüfung.

    Regeln (Prio absteigend):
      ask_maurice: >10 GB, unter /root/vault, enthält .git, active-service-Dropins
      safe_delete: /tmp Dateien >7 Tage, leere/obsolete Logs, docker reclaimable
      safe_archive: Backups >3 Tage, _DEPRECATED_, _archive, codex_backup_
      migrate_review: alte Projekte, Duplikate, nicht-referenzierte Repos
    """
    p = Path(c.path)
    size_gb = c.size_bytes / 1024**3

    # Hard rules: always ask for protected/system paths
    protected = ("/vault", "/etc", "/root/.", "/var/lib/docker", "/var/lib/systemd",
                 "/var/lib/snapd", "/snap", "/boot", "/usr", "/lib", "/proc", "/sys")
    if any(pat in c.path for pat in protected) or size_gb > 10:
        c.risk_class = "ask_maurice"
        c.action = "ask"
        c.confidence = 0.95
        c.evidence = "Protected/system path or >10 GB; human decision required"
        return c

    # Service names / active processes
    if c.path.endswith(".service") or c.path.endswith(".timer") or ".service.d" in c.path:
        c.risk_class = "ask_maurice"
        c.action = "ask"
        c.confidence = 0.95
        c.evidence = "Systemd unit or drop-in; never auto-modify"
        return c

    if c.category == "docker":
        c.risk_class = "safe_delete"
        c.action = "docker_prune"
        c.confidence = 0.9
        c.evidence = "Docker reclaimable space is safe to prune"
        return c

    if c.path.startswith("/root/_archive"):
        c.risk_class = "ask_maurice"
        c.action = "ask"
        c.confidence = 0.9
        c.evidence = "Already archived under /root/_archive; do not auto-move again"
        return c

    if c.category in ("old_backup", "deprecated"):
        name = Path(c.path).name
        base_name = name.split("-")[0].split("_")[0]
        if _is_active_project(name) or _is_active_project(base_name):
            c.risk_class = "ask_maurice"
            c.action = "ask"
            c.confidence = 0.9
            c.evidence = "Candidate relates to an active systemd service/process"
            return c
        # Nur echt als deprecated markierte Pfade
        if not any(prefix in c.path for prefix in ("_DEPRECATED_", "_archive", "codex_backup_", "legal_mac_pull_", "_backups")):
            c.risk_class = "ask_maurice"
            c.action = "ask"
            c.confidence = 0.85
            c.evidence = "Deprecated candidate is not in a known safe archive prefix"
            return c
        c.risk_class = "safe_archive"
        c.action = "archive_to_backup"
        c.confidence = 0.85
        c.evidence = f"Backup/deprecated object in safe archive prefix ({c.age_days:.1f} days)"
        return c

    if c.category == "log" and c.age_days > 7:
        c.risk_class = "safe_delete"
        c.action = "truncate_log"
        c.confidence = 0.8
        c.evidence = "Log older than 7 days can be truncated"
        return c

    if c.category in ("large_dir", "large_file") and c.age_days > 30 and "/tmp/" in c.path:
        c.risk_class = "safe_delete"
        c.action = "delete"
        c.confidence = 0.8
        c.evidence = "Old temporary data in /tmp"
        return c

    # Default: review by human
    c.risk_class = "ask_maurice"
    c.action = "ask"
    c.confidence = 0.6
    c.evidence = "No safe rule matched; needs review"
    return c


def classify_all(router: ReasoningRouter | None = None) -> list[Candidate]:
    candidates = []
    with open(CANDIDATES_PATH) as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                candidates.append(Candidate(**data))
    classified = []
    for c in candidates[:50]:  # Limitiere auf Top 50
        classified.append(classify_candidate(router, c))
    return classified


def propose_actions(candidates: list[Candidate]) -> list[Path]:
    proposals: list[Path] = []
    for c in candidates:
        if c.risk_class in ("safe_delete", "safe_archive"):
            name = f"housekeep-{c.category}-{Path(c.path).name[:40]}"
            cmd = f"python3 -m hecate.system_housekeeper apply {Path(c.path).name}"
            proposals.append(create_proposal(
                name=name,
                purpose=f"Housekeeping: {c.action} {c.path} ({c.size_bytes / 1024**3:.2f} GB)",
                schedule="einmalig",
                command=cmd,
            ))
        elif c.risk_class == "ask_maurice":
            # Telegram-Freigabe-Proposal
            name = f"housekeep-ask-{c.category}-{Path(c.path).name[:30]}"
            proposals.append(create_telegram_approval_proposal(c))
    return proposals


def create_telegram_approval_proposal(c: Candidate) -> Path:
    name = f"housekeep-ask-{c.category}-{Path(c.path).name[:30]}"
    body = f"""---
status: telegram_approval
loop: {name}
erstellt: durch hecate.system_housekeeper
telegram_approval: required
---

# Freigabe erforderlich: {c.action} {c.path}

**Kategorie:** {c.category}
**Grösse:** {c.size_bytes / 1024**3:.2f} GB
**Alter:** {c.age_days:.1f} Tage
**Begruendung:** {c.reason}
**Vorschlag des lokalen Classifiers:** {c.risk_class} ({c.confidence:.0%})
**Evidenz:** {c.evidence}

## Aktion
{c.action} auf {c.path}

## Sicherheitsmassnahmen
1. Backup vorher pruefen (nur bei migrate/archive)
2. Ledger-Eintrag nachher
3. Verify-Loop prueft Erfolg

## Freigabe
Antworte im Telegram mit `/approve {name}` oder `/deny {name}`.
"""
    path = Path("/root/projects/loop-master/proposals") / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 2
    while path.exists():
        path = path.parent / f"{name}-{n}.md"
        n += 1
    path.write_text(body, encoding="utf-8")
    return path


def apply_archive_or_delete(target_name: str) -> None:
    # Simplifizierte Version: liest candidate aus Log, archiviert oder löscht
    raise NotImplementedError("apply requires candidate lookup + safety gate")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 -m hecate.system_housekeeper scan | classify | propose")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "scan":
        items = scan_all()
        print(f"{len(items)} candidates written to {CANDIDATES_PATH}")
    elif cmd == "classify":
        items = classify_all()
        with open(CANDIDATES_PATH, "w", encoding="utf-8") as f:
            for c in items:
                f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")
        print(f"{len(items)} candidates classified")
    elif cmd == "propose":
        items = [Candidate(**json.loads(line)) for line in open(CANDIDATES_PATH) if line.strip()]
        paths = propose_actions(items)
        print(f"{len(paths)} proposals created")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
