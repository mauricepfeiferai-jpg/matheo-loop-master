#!/usr/bin/env python3
"""hecate.orchestrator — Hermes-driven agent orchestrator.

Reads the canonical agent roster and routes read-only smoke tasks to each
agent via the HECATE agent bridge. Produces a consolidated run report and
records every run in the Learning Ledger.

This is NOT an autonomous loop. It is a manually-invoked orchestrator that
runs through a configured set of agents and reports back. Mutating actions
still require explicit Maurice GO through the Policy Guard.

Usage:
  python3 -m hecate.orchestrator --run-all
  python3 -m hecate.orchestrator --agents operator,digest,policy_guard
  python3 -m hecate.orchestrator --dry-run
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from hecate.learning_ledger import LearningLedger

ORCHESTRATOR_VERSION = "1.0"
REPORTS_DIR = Path("reports")

AGENTS = [
    "hetzner_operator",
    "hetzner_sensor",
    "hetzner_digest",
    "hetzner_policy_guard",
    "hetzner_scout",
    "hetzner_archivist",
    "hetzner_cost_guard",
    "hetzner_security_scanner",
    "hetzner_backup_checker",
    "hetzner_performance_profiler",
    "mac_builder",
    "mac_reviewer",
    "mac_strategist",
]

AGENT_TO_SMOKE = {
    "hetzner_operator": "operator",
    "hetzner_sensor": "sensor",
    "hetzner_digest": "digest",
    "hetzner_policy_guard": "policy_guard",
    "hetzner_scout": "scout",
    "hetzner_archivist": "archivist",
    "hetzner_cost_guard": "cost_guard",
    "hetzner_security_scanner": "security_scanner",
    "hetzner_backup_checker": "backup_checker",
    "hetzner_performance_profiler": "performance_profiler",
    "mac_builder": "builder",
    "mac_reviewer": "reviewer",
    "mac_strategist": "strategist",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_smoke(agent_smoke: str) -> dict:
    """Invoke a single agent smoke command and return structured result."""
    cmd = ["python3", "-m", "hecate.agent_smoke", agent_smoke]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            cwd=str(Path(__file__).parent.parent),
        )
        return {
            "agent_smoke": agent_smoke,
            "rc": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "ok": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "agent_smoke": agent_smoke,
            "rc": -1,
            "stdout": "",
            "stderr": "timeout",
            "ok": False,
        }
    except Exception as exc:
        return {
            "agent_smoke": agent_smoke,
            "rc": -1,
            "stdout": "",
            "stderr": str(exc),
            "ok": False,
        }


def _record_orchestrator_run(results: list[dict], agents: list[str]) -> str | None:
    """Record the orchestrator run in the Learning Ledger."""
    try:
        ll = LearningLedger()
        ok_count = sum(1 for r in results if r["ok"])
        trace_id = ll.record(
            goal=f"orchestrator run for {len(agents)} agents",
            agent_action=f"ran {len(agents)} smoke agents, {ok_count} ok",
            model_used="rules/local",
            context=json.dumps({"agents": agents, "ok": ok_count, "fail": len(results) - ok_count}),
            business_outcome="orchestrator_pilot",
            reusable_pattern="",
            eval_scores={"ok_rate": ok_count / len(results) if results else 0.0},
        )
        return trace_id
    except Exception:
        return None


def run_orchestrator(agents: list[str], dry_run: bool = False) -> dict:
    """Run smoke commands for a list of agents and produce a report."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now().replace(":", "-")
    report_path = REPORTS_DIR / f"orchestrator_run_{ts}.md"

    results: list[dict] = []
    for agent in agents:
        smoke = AGENT_TO_SMOKE.get(agent)
        if not smoke:
            results.append({"agent": agent, "agent_smoke": "unknown", "ok": False, "stderr": "No smoke mapping", "rc": -1, "stdout": ""})
            continue

        if dry_run:
            results.append({"agent": agent, "agent_smoke": smoke, "ok": True, "stdout": "dry-run", "stderr": "", "rc": 0})
            continue

        res = _run_smoke(smoke)
        res["agent"] = agent
        results.append(res)

    ok_count = sum(1 for r in results if r["ok"])
    trace_id = _record_orchestrator_run(results, agents)

    lines = [
        f"# HECATE Orchestrator Run — {ts}",
        "",
        f"**Agents:** {len(agents)}",
        f"**OK:** {ok_count} / {len(agents)}",
        f"**Trace ID:** {trace_id or 'unavailable'}",
        "",
        "## Results",
    ]
    for r in results:
        marker = "🟢" if r["ok"] else "🔴"
        lines.append(f"- {marker} `{r['agent']}` (`{r['agent_smoke']}`) — exit {r['rc']}")
        if r["stdout"]:
            lines.append(f"  - stdout: `{r['stdout'][:120]}`")
        if r["stderr"]:
            lines.append(f"  - stderr: `{r['stderr'][:120]}`")

    lines.extend(["", "## Safety Note"])
    lines.append("- Only read-only smoke commands were invoked. No mutations, no Telegram, no cron.")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "ok": ok_count == len(agents),
        "report": str(report_path),
        "trace_id": trace_id,
        "ok_count": ok_count,
        "total": len(agents),
        "results": results,
        "ts": ts,
    }


def _cli() -> int:
    parser = argparse.ArgumentParser(description="HECATE Agent Orchestrator")
    parser.add_argument("--agents", default="", help="Comma-separated agent names (default: all)")
    parser.add_argument("--run-all", action="store_true", help="Run all 13 agents")
    parser.add_argument("--dry-run", action="store_true", help="List what would run without executing")
    parser.add_argument("--count", type=int, default=0, help="Run at least N agents (default: 0 = use --agents/--run-all)")
    args = parser.parse_args()

    if args.run_all:
        agents = AGENTS[:]
    elif args.agents:
        agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    elif args.count > 0:
        agents = AGENTS[: args.count]
    else:
        parser.print_help()
        return 1

    unknown = set(agents) - set(AGENTS)
    if unknown:
        print(json.dumps({"ok": False, "error": f"Unknown agents: {sorted(unknown)}. Allowed: {AGENTS}"}, indent=2))
        return 1

    result = run_orchestrator(agents, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(_cli())
