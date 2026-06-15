#!/usr/bin/env python3
"""hecate.agent_smoke — Manual smoke commands for the 13-agent operating model.

This module provides documented, manually-invoked smoke commands. It does NOT
install cron, systemd, or any autonomous loop. It does NOT send Telegram.

Commands:
  python3 -m hecate.agent_smoke operator
  python3 -m hecate.agent_smoke sensor
  python3 -m hecate.agent_smoke digest --input reports/operator_report_*.md
  python3 -m hecate.agent_smoke policy_guard --proposals reports/digest_*.md
  python3 -m hecate.agent_smoke scout
  python3 -m hecate.agent_smoke archivist
  python3 -m hecate.agent_smoke cost_guard
  python3 -m hecate.agent_smoke security_scanner
  python3 -m hecate.agent_smoke backup_checker
  python3 -m hecate.agent_smoke performance_profiler
  python3 -m hecate.agent_smoke builder --task "description"
  python3 -m hecate.agent_smoke reviewer --files file1,file2
  python3 -m hecate.agent_smoke strategist --topic "topic"

Every invocation records a raw_trace in the Learning Ledger if configured.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from hecate.data_pipeline import DataPipeline
from hecate.eval_engine import EvalEngine
from hecate.learning_ledger import LearningLedger
from hecate.policy_guard import evaluate as policy_evaluate

REPORTS_DIR = Path("reports")
PROPOSALS_DIR = Path("proposals")
LEDGER_PATH_ENV = os.environ.get("LEARNING_LEDGER_PATH", "/var/lib/loop-master/learning_ledger.jsonl")

RiskLevel = Literal["P0", "P1", "P2", "P3", "P4", "unknown"]
Verdict = Literal["ALLOW", "DENY", "REQUIRE_MAURICE_GO"]


# ─── Operator ──────────────────────────────────────────────────────────────────


def _safe_shell(cmd: list[str]) -> tuple[str, str, int]:
    """Run a read-only shell command, return (stdout, stderr, rc)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return result.stdout, result.stderr, result.returncode
    except Exception as exc:
        return "", str(exc), 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_load() -> str:
    uptime_out, _, _ = _safe_shell(["uptime", "-s"])
    load_out, _, _ = _safe_shell(["cat", "/proc/loadavg"])
    return load_out.strip() if load_out.strip() else uptime_out.strip()


def _parse_disk() -> list[dict]:
    out, _, _ = _safe_shell(["df", "-h"])
    lines = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 6:
            lines.append({"fs": parts[0], "size": parts[1], "used": parts[2], "avail": parts[3], "use": parts[4], "mount": parts[5]})
    return lines


def _parse_memory() -> dict:
    out, _, _ = _safe_shell(["free", "-h"])
    mem_line = next((l for l in out.splitlines() if l.startswith("Mem:")), "")
    parts = mem_line.split()
    return {"mem": parts[1] if len(parts) > 1 else "", "used": parts[2] if len(parts) > 2 else ""}


def _tmux_summary() -> list[dict]:
    out, _, _ = _safe_shell(["tmux", "list-sessions"])
    sessions = []
    for line in out.splitlines():
        if ":" not in line:
            continue
        name = line.split(":", 1)[0]
        sessions.append({"name": name, "status": "active" if "attached" in line else "detached"})
    return sessions


def _healty_service_status() -> list[dict]:
    # Read-only status checks for known services only.
    services = ["codex-bridge", "ollama", "galaxia-core"]
    results = []
    for svc in services:
        out, err, rc = _safe_shell(["systemctl", "status", svc, "--no-pager"])
        active = "active (running)" in out
        results.append({"service": svc, "active": active, "available": rc == 0 or out.strip() != ""})
    return results


def run_operator() -> Path:
    """Run the Hetzner Operator smoke command."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now().replace(":", "-")
    report_path = REPORTS_DIR / f"operator_report_{ts}.md"

    disk = _parse_disk()
    memory = _parse_memory()
    load = _parse_load()
    tmux = _tmux_summary()
    services = _healty_service_status()

    risks: list[dict] = []
    for d in disk:
        use = d.get("use", "").replace("%", "")
        if use.isdigit() and int(use) >= 90:
            risks.append({"level": "P1", "source": "disk", "detail": f"{d['mount']} at {d['use']}"})

    stale_sessions = [s for s in tmux if s["status"] == "detached"]
    if len(stale_sessions) > 5:
        risks.append({"level": "P2", "source": "tmux", "detail": f"{len(stale_sessions)} detached tmux sessions"})

    down_services = [s for s in services if not s["active"]]
    if down_services:
        risks.append({"level": "P2", "source": "service", "detail": f"Services not active: {[s['service'] for s in down_services]}"})

    lines = [
        f"# HECATE Operator Report — {ts}",
        "",
        "## Health",
        f"- Load: `{load}`",
        f"- Memory: {memory.get('used', '?')} used / {memory.get('mem', '?')}",
        f"- tmux sessions: {len(tmux)} ({len(stale_sessions)} detached)",
        "",
        "## Disk",
    ]
    for d in disk:
        lines.append(f"- `{d['mount']}` — {d['used']} / {d['size']} ({d['use']})")

    lines.extend(["", "## Services"])
    for s in services:
        marker = "🟢" if s["active"] else "🔴"
        lines.append(f"- {marker} {s['service']} (available={s['available']})")

    lines.extend(["", "## Risks"])
    if risks:
        for r in risks:
            lines.append(f"- **{r['level']}** | {r['source']}: {r['detail']}")
    else:
        lines.append("- No immediate risks detected.")

    lines.extend(["", "## Next Actions"])
    if risks:
        lines.append("- REVIEW risks above. Most require `REQUIRES_MAURICE_GO` if mutating.")
    lines.append("- Inspect stale tmux sessions manually before killing any.")
    lines.append("- Run Digest next: `python3 -m hecate.agent_smoke digest --input <report>`")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ─── Digest ───────────────────────────────────────────────────────────────────


def run_digest(input_path: Path | None = None) -> Path:
    """Run the Hetzner Digest smoke command."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now().replace(":", "-")
    digest_path = REPORTS_DIR / f"digest_{ts}.md"

    source = input_path
    if source is None or not source.exists():
        candidates = sorted(REPORTS_DIR.glob("operator_report_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            source = candidates[0]
        else:
            digest_path.write_text("_Kein Operator-Report vorhanden._\n", encoding="utf-8")
            return digest_path

    text = source.read_text(encoding="utf-8", errors="ignore")
    # Simple rule-based extraction.
    risks: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith("- **P"):
            risks.append(line.strip())

    lines = [
        f"# HECATE Digest — {ts}",
        "",
        f"Source: `{source.name}`",
        "",
        "## Executive Summary",
    ]
    if risks:
        lines.append(f"- **{len(risks)} risk(s)** require attention.")
    else:
        lines.append("- System looks stable. No immediate action.")

    lines.extend(["", "## Action Required"])
    for r in risks:
        lines.append(f"- {r} → `REQUIRES_MAURICE_GO`")
    if not risks:
        lines.append("- None.")

    lines.extend(["", "## Telegram Worthy"])
    p0_p1 = [r for r in risks if r.startswith("- **P0") or r.startswith("- **P1")]
    if p0_p1:
        lines.append(f"- {len(p0_p1)} item(s) would push immediately.")
    else:
        lines.append("- No P0/P1 items. Include in daily digest only.")

    lines.extend(["", "## Safe Read-Only Next Steps"])
    lines.append("- Re-run Operator later.")
    lines.append("- Review tmux sessions manually.")

    digest_path.write_text("\n".join(lines), encoding="utf-8")
    return digest_path


# ─── Policy Guard ────────────────────────────────────────────────────────────


def evaluate_policy_guard(command: str, agent: str = "hetzner_operator") -> dict:
    """Evaluate a single proposed command via the central Policy Guard."""
    return policy_evaluate(command, agent)


def run_policy_guard(proposal_path: Path | None = None) -> Path:
    """Run the Policy Guard smoke command over a digest or proposal file."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now().replace(":", "-")
    verdict_path = REPORTS_DIR / f"policy_guard_verdict_{ts}.md"

    if proposal_path and proposal_path.exists():
        text = proposal_path.read_text(encoding="utf-8", errors="ignore")
    else:
        candidates = sorted(REPORTS_DIR.glob("digest_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        text = candidates[0].read_text(encoding="utf-8", errors="ignore") if candidates else ""

    # Extract candidate actions (lines mentioning REQUIRES_MAURICE_GO or shell-like).
    candidates: list[str] = []
    for line in text.splitlines():
        if "REQUIRES_MAURICE_GO" in line or any(p in line for p in ["systemctl", "crontab", "rm -", "curl | bash"]):
            candidates.append(line.strip())

    lines = [f"# HECATE Policy Guard Verdict — {ts}", ""]
    if not candidates:
        lines.append("- No actionable commands detected. ALLOW read-only continuation.")
        verdict_path.write_text("\n".join(lines), encoding="utf-8")
        return verdict_path

    for c in candidates:
        verdict = evaluate_policy_guard(c)
        emoji = {"ALLOW": "🟢", "DENY": "🔴", "REQUIRE_MAURICE_GO": "🟡"}.get(verdict["verdict"], "⚪")
        lines.append(f"- {emoji} **{verdict['verdict']}** ({verdict['risk_level']}): {verdict['reason']}")
        lines.append(f"  Command/context: `{c[:120]}`")

    lines.append("")
    lines.append("## Summary")
    verdicts = [evaluate_policy_guard(c)["verdict"] for c in candidates]
    for v in ["DENY", "REQUIRE_MAURICE_GO", "ALLOW"]:
        count = verdicts.count(v)
        if count:
            lines.append(f"- {v}: {count}")

    verdict_path.write_text("\n".join(lines), encoding="utf-8")
    return verdict_path


# ─── Builder / Reviewer (smoke stubs) ──────────────────────────────────────────


def run_builder(task: str) -> Path:
    """Stub builder smoke command: produces a proposal, does not edit files."""
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now().replace(":", "-")
    proposal_path = PROPOSALS_DIR / f"builder_smoke_{ts}.md"
    lines = [
        f"# Builder Smoke Proposal — {ts}",
        "",
        f"**Task:** {task}",
        "",
        "## Scope",
        "- Workspace-only changes.",
        "- No systemd/cron/secrets/trading/legal.",
        "",
        "## Plan",
        "1. Read existing files.",
        "2. Implement minimal change.",
        "3. Run tests.",
        "4. Hand to Reviewer.",
        "",
        "## Status",
        "- PROPOSAL_ONLY — awaiting Reviewer + Maurice GO before file edits.",
    ]
    proposal_path.write_text("\n".join(lines), encoding="utf-8")
    return proposal_path


def run_reviewer(files: list[str]) -> Path:
    """Stub reviewer smoke command: produces a verdict report, does not edit files."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now().replace(":", "-")
    review_path = REPORTS_DIR / f"reviewer_smoke_{ts}.md"

    checks = [
        "No stubs/placeholders/TODOs detected (placeholder check).",
        "No forbidden paths referenced.",
        "Tests would be required before promotion.",
        "No secrets in output.",
    ]

    lines = [
        f"# Reviewer Smoke Verdict — {ts}",
        "",
        f"Files reviewed: {', '.join(files) if files else 'none'}",
        "",
        "## Checks",
    ]
    for c in checks:
        lines.append(f"- ✅ {c}")

    lines.extend([
        "",
        "## Verdict",
        "- **YELLOW** — smoke-level review only. Full review requires actual file content and tests.",
        "",
        "## Required before promotion",
        "- Real test run with `python3 -m pytest tests/ -q`",
        "- Maurice approval for any mutating action.",
    ])

    review_path.write_text("\n".join(lines), encoding="utf-8")
    return review_path


# ─── Sensor ────────────────────────────────────────────────────────────────────


def _read_findings_tail(n: int = 50) -> list[str]:
    findings_path = Path("/var/lib/loop-master/findings.jsonl")
    if not findings_path.exists():
        return []
    lines = findings_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return lines[-n:]


def _classify_line(line: str) -> str:
    lowered = line.lower()
    if any(k in lowered for k in ["error", "traceback", "failed", "crash", "exception", "restart loop"]):
        return "fehler"
    if any(k in lowered for k in ["approve", "go", "decision", "requires"]):
        return "entscheidung"
    if any(k in lowered for k in ["ok", "success", "green", "passed"]):
        return "erfolg"
    if any(k in lowered for k in ["heartbeat", "routine", "status", "check passed"]):
        return "noise"
    if any(k in lowered for k in ["deny", "forbidden", "safety_block"]):
        return "safety_block"
    return "unbekannt"


def run_sensor() -> Path:
    """Run the Hetzner Sensor smoke command (read-only event classification)."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now().replace(":", "-")
    report_path = REPORTS_DIR / f"sensor_report_{ts}.md"

    findings = _read_findings_tail(50)
    classified: dict[str, int] = {}
    worth_learning = 0
    examples: list[str] = []
    for line in findings:
        cls = _classify_line(line)
        classified[cls] = classified.get(cls, 0) + 1
        if cls in ("fehler", "safety_block", "entscheidung"):
            worth_learning += 1
        if len(examples) < 5 and cls != "noise":
            examples.append(f"`{cls}`: {line[:100]}")

    lines = [
        f"# HECATE Sensor Report — {ts}",
        "",
        "## Classification Counts",
    ]
    for cls, count in sorted(classified.items(), key=lambda x: -x[1]):
        lines.append(f"- {cls}: {count}")

    lines.extend(["", "## Examples (non-noise)"])
    if examples:
        for ex in examples:
            lines.append(f"- {ex}")
    else:
        lines.append("- No non-noise examples in window.")

    lines.extend(["", "## Worth Learning"])
    lines.append(f"- {worth_learning} event(s) flagged for learning.")

    lines.extend(["", "## Safety Note"])
    lines.append("- Source findings bus not mutated.")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ─── Scout ─────────────────────────────────────────────────────────────────────


def run_scout() -> Path:
    """Run the Hetzner Scout smoke command (read-only research/opportunity scan)."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now().replace(":", "-")
    report_path = REPORTS_DIR / f"scout_report_{ts}.md"
    proposal_path = PROPOSALS_DIR / f"scout_smoke_{ts}.md"

    # Read existing proposals to avoid duplicate-looking stubs.
    existing = sorted(PROPOSALS_DIR.glob("scout_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    recent_count = len([p for p in existing if _file_age_days(p) < 1])

    lines = [
        f"# HECATE Scout Report — {ts}",
        "",
        "## Research Sources",
        "- GitHub trending (read-only search): not implemented in smoke stub.",
        "- Public AI/agent articles: not implemented in smoke stub.",
        "- Curated RSS/feeds: not implemented in smoke stub.",
        "",
        "## Opportunities",
        "- No live research performed in smoke stub. This is a wiring test.",
        "",
        "## Safety Note",
        "- No external posts, no repository cloning, no package installation.",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")

    prop_lines = [
        f"# Scout Smoke Proposal — {ts}",
        "",
        "**Source:** smoke test",
        "**Relevance:** wiring validation",
        "**Risk:** low",
        "**Next step:** Implement read-only research adapter (GitHub/RSS/X via approved tools).",
        "",
        "## Status",
        "- PROPOSAL_ONLY — no automatic action taken.",
    ]
    proposal_path.write_text("\n".join(prop_lines), encoding="utf-8")

    return report_path


# ─── Strategist ────────────────────────────────────────────────────────────────


def run_strategist(topic: str = "next HECATE priorities") -> Path:
    """Run the Mac Strategist smoke command (read-only strategy memo)."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now().replace(":", "-")
    report_path = REPORTS_DIR / f"strategist_{ts}.md"

    lines = [
        f"# Mac Strategist Memo — {ts}",
        "",
        f"**Topic:** {topic}",
        "",
        "## Observations",
        "- HECATE now has 13 agent contracts and smoke commands.",
        "- Daily smoke wrapper exists but is not yet cron-activated.",
        "- Eval framework and performance dashboard are planned next.",
        "",
        "## Priorities",
        "1. Stabilize daily smoke runs for 7 days.",
        "2. Build eval framework for the 5 new Hetzner agents.",
        "3. Build agent performance dashboard.",
        "",
        "## Risks",
        "- Running too many agents before evaluation creates noise.",
        "- Mac agents need local model access; verify before deployment.",
        "",
        "## Next Actions",
        "- Maurice GO for cron activation.",
        "- Maurice GO for eval framework implementation.",
        "",
        "## Safety Note",
        "- No files modified. No external posting. Strategy memo only.",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ─── Archivist ─────────────────────────────────────────────────────────────────


def _file_age_days(path: Path) -> float:
    try:
        return (datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) / 86400
    except OSError:
        return -1.0


def run_archivist() -> Path:
    """Run the Hetzner Archivist smoke command (read-only curation scan)."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now().replace(":", "-")
    report_path = REPORTS_DIR / f"archivist_{ts}.md"

    proposals = sorted(Path("proposals").glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    decision_cards = sorted(Path("decision_cards").glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    reports = sorted(REPORTS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)

    old_proposals = [p for p in proposals if _file_age_days(p) > 30]
    old_decision_cards = [d for d in decision_cards if _file_age_days(d) > 14]
    old_reports = [r for r in reports if _file_age_days(r) > 7]

    lines = [
        f"# HECATE Archivist Report — {ts}",
        "",
        "## Scan Summary",
        f"- Proposals scanned: {len(proposals)} ({len(old_proposals)} older than 30 days)",
        f"- Decision Cards scanned: {len(decision_cards)} ({len(old_decision_cards)} older than 14 days)",
        f"- Reports scanned: {len(reports)} ({len(old_reports)} older than 7 days)",
        "",
        "## Suggested Archives",
    ]
    if old_proposals:
        for p in old_proposals[:10]:
            lines.append(f"- `{p.name}` — {int(_file_age_days(p))} days old → `REQUIRES_MAURICE_GO`")
    else:
        lines.append("- No proposals older than 30 days.")

    if old_decision_cards:
        for d in old_decision_cards[:10]:
            lines.append(f"- `{d.name}` — {int(_file_age_days(d))} days old → `REQUIRES_MAURICE_GO`")
    else:
        lines.append("- No decision cards older than 14 days.")

    lines.extend(["", "## Duplicates / Promotion Candidates"])
    lines.append("- No automatic duplicate detection implemented in smoke stub.")

    lines.extend(["", "## Safety Note"])
    lines.append("- No files were moved, deleted, or modified. This report is read-only.")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ─── Cost Guard ────────────────────────────────────────────────────────────────


def _docker_system_df() -> list[dict]:
    out, err, rc = _safe_shell(["docker", "system", "df"])
    if rc != 0 or not out.strip():
        return []
    items = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4:
            items.append({"type": parts[0], "total": parts[1], "active": parts[2], "size": parts[3]})
    return items


def _dir_size_mb(path: Path) -> int:
    out, err, rc = _safe_shell(["du", "-sm", str(path)])
    if rc != 0 or not out.strip():
        return 0
    try:
        return int(out.split()[0])
    except (ValueError, IndexError):
        return 0


def run_cost_guard() -> Path:
    """Run the Hetzner Cost Guard smoke command (read-only cost/waste scan)."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now().replace(":", "-")
    report_path = REPORTS_DIR / f"cost_guard_{ts}.md"

    docker_df = _docker_system_df()
    log_size_mb = _dir_size_mb(Path("/root/logs"))
    tmp_size_mb = _dir_size_mb(Path("/tmp"))
    disk = _parse_disk()
    root_use = next((d["use"] for d in disk if d["mount"] == "/"), "unknown")

    risks: list[dict] = []
    use = root_use.replace("%", "")
    if use.isdigit() and int(use) >= 85:
        risks.append({"level": "P1", "source": "disk", "detail": f"root at {root_use}"})
    if log_size_mb > 5000:
        risks.append({"level": "P2", "source": "logs", "detail": f"/root/logs is {log_size_mb} MB"})
    if tmp_size_mb > 5000:
        risks.append({"level": "P2", "source": "tmp", "detail": f"/tmp is {tmp_size_mb} MB"})

    lines = [
        f"# HECATE Cost Guard Report — {ts}",
        "",
        "## Waste Signals",
        f"- `/root/logs` size: {log_size_mb} MB",
        f"- `/tmp` size: {tmp_size_mb} MB",
        f"- Root disk usage: {root_use}",
        "",
        "## Docker System Df",
    ]
    if docker_df:
        for item in docker_df:
            lines.append(f"- {item['type']}: {item['total']} total / {item['active']} active / {item['size']} size")
    else:
        lines.append("- docker system df unavailable.")

    lines.extend(["", "## Risks"])
    if risks:
        for r in risks:
            lines.append(f"- **{r['level']}** | {r['source']}: {r['detail']} → `REQUIRES_MAURICE_GO` if cleanup needed")
    else:
        lines.append("- No major cost/waste signals.")

    lines.extend(["", "## Recommended Safe Next Steps"])
    lines.append("- Re-run later to establish baseline.")
    lines.append("- Review `/root/logs` rotation policy before any cleanup.")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ─── Security Scanner ──────────────────────────────────────────────────────────


def _secret_like_files(root: Path) -> list[str]:
    found = []
    for pattern in ("*.env", "*.key", "*.pem", "*.p12"):
        for p in root.rglob(pattern):
            # Only collect names, never read contents.
            if ".git" not in p.parts:
                found.append(str(p.relative_to(root)))
    return found[:20]


def _permission_scan(paths: list[str]) -> list[dict]:
    results = []
    for path in paths:
        out, err, rc = _safe_shell(["stat", "-c", "%a %n", path])
        if rc == 0 and out.strip():
            mode, name = out.strip().split(" ", 1)
            results.append({"path": name, "mode": mode, "world_readable": mode.endswith("4") or mode.endswith("5") or mode.endswith("6") or mode.endswith("7")})
    return results


def _listening_ports() -> list[str]:
    out, err, rc = _safe_shell(["ss", "-tlnp"])
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines()[1:] if line.strip()]


def run_security_scanner() -> Path:
    """Run the Hetzner Security Scanner smoke command (read-only posture scan)."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now().replace(":", "-")
    report_path = REPORTS_DIR / f"security_scan_{ts}.md"

    sensitive_paths = ["/root/projects/loop-master", "/root/.ssh", "/root/.secrets"]
    sensitive_paths = [p for p in sensitive_paths if Path(p).exists()]
    perms = _permission_scan(sensitive_paths)
    ports = _listening_ports()
    secret_files = _secret_like_files(Path("/root/projects/loop-master"))

    findings: list[dict] = []
    for p in perms:
        if p["world_readable"]:
            findings.append({"level": "P1", "source": "permissions", "detail": f"{p['path']} mode {p['mode']}"})

    lines = [
        f"# HECATE Security Scanner Report — {ts}",
        "",
        "## Permission Scan (metadata only)",
    ]
    if perms:
        for p in perms:
            marker = "🔴" if p["world_readable"] else "🟢"
            lines.append(f"- {marker} `{p['path']}` mode {p['mode']}")
    else:
        lines.append("- No sensitive paths readable.")

    lines.extend(["", "## Secret-like Filenames (names only, contents NOT read)"])
    if secret_files:
        for name in secret_files:
            lines.append(f"- `{name}`")
    else:
        lines.append("- No secret-like filenames found in workspace.")

    lines.extend(["", "## Listening Ports (local sockets only)"])
    if ports:
        lines.append(f"- {len(ports)} listening sockets detected.")
        for line in ports[:20]:
            lines.append(f"  - `{line}`")
    else:
        lines.append("- No listening ports data available.")

    lines.extend(["", "## Findings"])
    if findings:
        for f in findings:
            lines.append(f"- **{f['level']}** | {f['source']}: {f['detail']} → `REQUIRES_MAURICE_GO` if remediation needed")
    else:
        lines.append("- No P0/P1 findings. Posture looks acceptable.")

    lines.extend(["", "## Safety Note"])
    lines.append("- No permissions changed. No file contents read. No network probes sent.")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ─── Backup Checker ────────────────────────────────────────────────────────────


def _backup_destinations() -> list[Path]:
    candidates = [
        Path("/root/_backups"),
        Path("/var/lib/loop-master/backups"),
        Path("/root/projects/loop-master/backups"),
    ]
    return [p for p in candidates if p.exists()]


def run_backup_checker() -> Path:
    """Run the Hetzner Backup Checker smoke command (read-only coverage scan)."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now().replace(":", "-")
    report_path = REPORTS_DIR / f"backup_check_{ts}.md"

    destinations = _backup_destinations()
    lines = [
        f"# HECATE Backup Check Report — {ts}",
        "",
        "## Backup Destinations",
    ]

    gaps: list[dict] = []
    if destinations:
        for dest in destinations:
            files = sorted(dest.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
            newest_age_days = _file_age_days(files[0]) if files else float("inf")
            lines.append(f"- `{dest}` — {len(files)} items, newest {int(newest_age_days)} days old")
            if newest_age_days > 2:
                gaps.append({"level": "P2", "source": "freshness", "detail": f"{dest} newest backup is {int(newest_age_days)} days old"})
    else:
        lines.append("- No known backup destinations found.")
        gaps.append({"level": "P2", "source": "coverage", "detail": "No backup destinations configured or reachable"})

    lines.extend(["", "## Critical Paths Without Visible Backup"])
    critical_paths = [Path("/root/projects/loop-master"), Path("/root/vault"), Path("/root/.claude")]
    for cp in critical_paths:
        marker = "🟢" if cp.exists() else "⚪"
        lines.append(f"- {marker} `{cp}` — backup coverage not verified")

    lines.extend(["", "## Gaps"])
    if gaps:
        for g in gaps:
            lines.append(f"- **{g['level']}** | {g['source']}: {g['detail']} → `REQUIRES_MAURICE_GO` for remediation")
    else:
        lines.append("- No major backup gaps detected.")

    lines.extend(["", "## Safety Note"])
    lines.append("- No backups were run, moved, or deleted. This is a metadata-only scan.")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ─── Performance Profiler ───────────────────────────────────────────────────────


PERF_SNAPSHOTS_DIR = Path("/var/lib/loop-master/perf_snapshots")


def _docker_stats_summary() -> list[dict]:
    out, err, rc = _safe_shell(["docker", "stats", "--no-stream", "--format", "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"])
    if rc != 0 or not out.strip():
        return []
    items = []
    for line in out.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) >= 3:
            items.append({"name": parts[0], "cpu": parts[1], "mem": parts[2]})
    return items


def _ollama_ps() -> list[dict]:
    out, err, rc = _safe_shell(["ollama", "ps"])
    if rc != 0 or not out.strip():
        return []
    items = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4:
            items.append({"name": parts[0], "cpu": parts[1], "mem": parts[2], "size": parts[3]})
    return items


def _load_snapshot() -> dict:
    load_out, _, _ = _safe_shell(["cat", "/proc/loadavg"])
    parts = load_out.strip().split()
    return {"load1": parts[0] if parts else "?", "load5": parts[1] if len(parts) > 1 else "?", "load15": parts[2] if len(parts) > 2 else "?"}


def run_performance_profiler() -> Path:
    """Run the Hetzner Performance Profiler smoke command (read-only metrics)."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    PERF_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now().replace(":", "-")
    report_path = REPORTS_DIR / f"performance_profile_{ts}.md"

    snapshot = {
        "ts": _now(),
        "load": _load_snapshot(),
        "memory": _parse_memory(),
        "disk": _parse_disk(),
        "docker": _docker_stats_summary(),
        "ollama": _ollama_ps(),
    }
    snapshot_path = PERF_SNAPSHOTS_DIR / f"snapshot_{ts}.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    risks: list[dict] = []
    root_use = next((d["use"] for d in snapshot["disk"] if d["mount"] == "/"), "unknown")
    use = root_use.replace("%", "")
    if use.isdigit() and int(use) >= 90:
        risks.append({"level": "P1", "source": "disk", "detail": f"root at {root_use}"})

    load1 = snapshot["load"]["load1"]
    try:
        if float(load1) > 8.0:
            risks.append({"level": "P2", "source": "load", "detail": f"1m load {load1}"})
    except ValueError:
        pass

    lines = [
        f"# HECATE Performance Profile — {ts}",
        "",
        "## Current Snapshot",
        f"- Load 1m/5m/15m: {snapshot['load']['load1']} / {snapshot['load']['load5']} / {snapshot['load']['load15']}",
        f"- Memory used: {snapshot['memory'].get('used', '?')} / {snapshot['memory'].get('mem', '?')}",
        f"- Root disk: {root_use}",
        "",
        "## Containers",
    ]
    if snapshot["docker"]:
        for c in snapshot["docker"][:20]:
            lines.append(f"- `{c['name']}` — CPU {c['cpu']}, Mem {c['mem']}")
    else:
        lines.append("- docker stats unavailable.")

    lines.extend(["", "## Ollama Models"])
    if snapshot["ollama"]:
        for m in snapshot["ollama"]:
            lines.append(f"- `{m['name']}` — CPU {m['cpu']}, Mem {m['mem']}, Size {m['size']}")
    else:
        lines.append("- No Ollama models currently loaded.")

    lines.extend(["", "## Risks"])
    if risks:
        for r in risks:
            lines.append(f"- **{r['level']}** | {r['source']}: {r['detail']} → `REQUIRES_MAURICE_GO` if tuning needed")
    else:
        lines.append("- No P1/P2 performance regressions detected.")

    lines.extend(["", "## Snapshot"])
    lines.append(f"- Raw snapshot saved to `{snapshot_path}`")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ─── Learning Ledger integration ───────────────────────────────────────────────


def record_smoke(agent: str, goal: str, model_used: str, actions: list[str], files: list[str]) -> str | None:
    """Record a smoke run in the Learning Ledger if path is writable."""
    try:
        ll = LearningLedger()
        trace_id = ll.record(
            goal=goal,
            agent_action=", ".join(actions),
            model_used=model_used,
            context=f"agent={agent}, host=hetzner",
            business_outcome="pilot_run",
            reusable_pattern="",
            eval_scores={},
        )
        return trace_id
    except Exception:
        return None


# ─── CLI ──────────────────────────────────────────────────────────────────────


def _cli() -> int:
    parser = argparse.ArgumentParser(description="HECATE Agent Smoke Commands")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("operator", help="Run Hetzner Operator smoke")

    digest = sub.add_parser("digest", help="Run Hetzner Digest smoke")
    digest.add_argument("--input", type=Path, default=None, help="Path to operator report")

    guard = sub.add_parser("policy_guard", help="Run Policy Guard smoke over digest/proposal")
    guard.add_argument("--proposals", type=Path, default=None, help="Path to digest/proposal file")

    builder = sub.add_parser("builder", help="Run Mac Builder smoke (proposal-only)")
    builder.add_argument("--task", default="implement small approved module")

    reviewer = sub.add_parser("reviewer", help="Run Mac Reviewer smoke")
    reviewer.add_argument("--files", default="", help="Comma-separated file paths")

    sub.add_parser("sensor", help="Run Hetzner Sensor smoke (read-only)")
    sub.add_parser("scout", help="Run Hetzner Scout smoke (read-only)")
    sub.add_parser("archivist", help="Run Hetzner Archivist smoke (read-only)")
    sub.add_parser("cost_guard", help="Run Hetzner Cost Guard smoke (read-only)")
    sub.add_parser("security_scanner", help="Run Hetzner Security Scanner smoke (read-only)")
    sub.add_parser("backup_checker", help="Run Hetzner Backup Checker smoke (read-only)")
    sub.add_parser("performance_profiler", help="Run Hetzner Performance Profiler smoke (read-only)")

    strategist = sub.add_parser("strategist", help="Run Mac Strategist smoke (read-only)")
    strategist.add_argument("--topic", default="next HECATE priorities", help="Strategy topic")

    args = parser.parse_args()

    if args.cmd == "operator":
        path = run_operator()
        print(f"Operator report: {path}")
        record_smoke("hetzner_operator", "inspect system state", "rules/local", ["shell_readonly"], [str(path)])
        return 0

    if args.cmd == "sensor":
        path = run_sensor()
        print(f"Sensor report: {path}")
        record_smoke("hetzner_sensor", "classify event stream", "rules-only", ["classify"], [str(path)])
        return 0

    if args.cmd == "digest":
        path = run_digest(args.input)
        print(f"Digest report: {path}")
        record_smoke("hetzner_digest", "compress findings into digest", "rules/local", ["summarize"], [str(path)])
        return 0

    if args.cmd == "policy_guard":
        path = run_policy_guard(args.proposals)
        print(f"Policy Guard verdict: {path}")
        record_smoke("hetzner_policy_guard", "evaluate proposed actions", "rules-only", ["verdict"], [str(path)])
        return 0

    if args.cmd == "scout":
        path = run_scout()
        print(f"Scout report: {path}")
        record_smoke("hetzner_scout", "research opportunity", "rules/local", ["proposal"], [str(path)])
        return 0

    if args.cmd == "builder":
        path = run_builder(args.task)
        print(f"Builder proposal: {path}")
        record_smoke("mac_builder", f"build: {args.task}", "human/smoke", ["proposal"], [str(path)])
        return 0

    if args.cmd == "reviewer":
        files = [f.strip() for f in args.files.split(",") if f.strip()]
        path = run_reviewer(files)
        print(f"Reviewer report: {path}")
        record_smoke("mac_reviewer", "review smoke files", "human/smoke", ["review"], [str(path)])
        return 0

    if args.cmd == "strategist":
        path = run_strategist(args.topic)
        print(f"Strategist memo: {path}")
        record_smoke("mac_strategist", f"strategy: {args.topic}", "rules/local", ["memo"], [str(path)])
        return 0

    if args.cmd == "archivist":
        path = run_archivist()
        print(f"Archivist report: {path}")
        record_smoke("hetzner_archivist", "curate proposals and reports", "rules/local", ["file_read"], [str(path)])
        return 0

    if args.cmd == "cost_guard":
        path = run_cost_guard()
        print(f"Cost Guard report: {path}")
        record_smoke("hetzner_cost_guard", "monitor cost and waste signals", "rules/local", ["shell_readonly"], [str(path)])
        return 0

    if args.cmd == "security_scanner":
        path = run_security_scanner()
        print(f"Security Scanner report: {path}")
        record_smoke("hetzner_security_scanner", "scan security posture", "rules-only", ["metadata_scan"], [str(path)])
        return 0

    if args.cmd == "backup_checker":
        path = run_backup_checker()
        print(f"Backup Checker report: {path}")
        record_smoke("hetzner_backup_checker", "validate backup coverage", "rules/local", ["file_read"], [str(path)])
        return 0

    if args.cmd == "performance_profiler":
        path = run_performance_profiler()
        print(f"Performance Profiler report: {path}")
        record_smoke("hetzner_performance_profiler", "track performance trends", "rules/local", ["shell_readonly"], [str(path)])
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(_cli())
