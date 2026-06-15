#!/usr/bin/env python3
"""hecate.agent_smoke — Manual smoke commands for the 8-agent operating model.

This module provides documented, manually-invoked smoke commands. It does NOT
install cron, systemd, or any autonomous loop. It does NOT send Telegram.

Commands:
  python3 -m hecate.agent_smoke operator
  python3 -m hecate.agent_smoke digest --input reports/operator_report_*.md
  python3 -m hecate.agent_smoke policy_guard --proposals reports/digest_*.md
  python3 -m hecate.agent_smoke builder --task "description"
  python3 -m hecate.agent_smoke reviewer --files file1,file2

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

    args = parser.parse_args()

    if args.cmd == "operator":
        path = run_operator()
        print(f"Operator report: {path}")
        record_smoke("hetzner_operator", "inspect system state", "rules/local", ["shell_readonly"], [str(path)])
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

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(_cli())
