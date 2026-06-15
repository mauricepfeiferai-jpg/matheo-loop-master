#!/usr/bin/env python3
"""hecate.agent_bridge — Central gateway normalizer for all agent entrypoints.

Hermes, OpenClaw, and Claude Code all route tasks through this bridge.
The bridge:
1. Validates task schema
2. Routes to the correct HECATE agent
3. Enforces Policy Guard before execution
4. Records every run in the Learning Ledger
5. Returns a structured response

The bridge does NOT execute shell commands directly. Delegation only.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from hecate.learning_ledger import LearningLedger
from hecate.policy_guard import evaluate, load_permission_matrix

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

SOURCES = Literal["hermes", "openclaw", "claude", "manual"]


@dataclass
class AgentTask:
    source: SOURCES
    agent: str
    goal: str
    context: str = ""
    input_data: dict = field(default_factory=dict)
    approved_by: str = ""
    dry_run: bool = False
    requested_command: str = ""

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "agent": self.agent,
            "goal": self.goal,
            "context": self.context,
            "input_data": self.input_data,
            "approved_by": self.approved_by,
            "dry_run": self.dry_run,
            "requested_command": self.requested_command,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_task(task: AgentTask) -> tuple[bool, str]:
    """Validate incoming task. Returns (ok, error_message)."""
    if task.agent not in AGENTS:
        return False, f"Unknown agent: {task.agent}. Allowed: {AGENTS}"
    if not task.goal.strip():
        return False, "Task goal is required"
    if task.source not in ("hermes", "openclaw", "claude", "manual"):
        return False, f"Unknown source: {task.source}"
    return True, ""


def route_task(task: AgentTask) -> dict:
    """Route a validated task through Policy Guard and return result.

    Does not execute mutating commands unless approved_by is set and
    Policy Guard returns ALLOW or REQUIRE_MAURICE_GO with explicit approval.
    """
    matrix = load_permission_matrix()

    # Policy Guard check on the requested command or goal.
    command = task.requested_command or task.goal
    verdict = evaluate(command, task.agent, task.context, matrix)

    # If a command is requested and GO is required, we need explicit approval.
    if verdict["verdict"] == "REQUIRE_MAURICE_GO" and not task.approved_by:
        return {
            "ok": False,
            "verdict": verdict,
            "message": "Task requires explicit Maurice GO. Set approved_by and retry.",
            "proposal": task.to_dict(),
            "ts": _now(),
        }

    if verdict["verdict"] == "DENY":
        return {
            "ok": False,
            "verdict": verdict,
            "message": "Task denied by Policy Guard.",
            "proposal": task.to_dict(),
            "ts": _now(),
        }

    # Record in Learning Ledger.
    ll = LearningLedger()
    trace_id = ll.record(
        goal=task.goal,
        agent_action=f"route from {task.source} to {task.agent}",
        model_used="rules/policy_guard",
        context=json.dumps(task.to_dict(), ensure_ascii=False),
        business_outcome="routed" if not task.dry_run else "dry_run",
        reusable_pattern="",
        eval_scores={"policy_verdict": verdict["verdict"], "risk_level": verdict["risk_level"]},
    )

    if task.dry_run:
        return {
            "ok": True,
            "verdict": verdict,
            "message": "Dry run: task would be routed.",
            "trace_id": trace_id,
            "proposal": task.to_dict(),
            "ts": _now(),
        }

    return {
        "ok": True,
        "verdict": verdict,
        "message": f"Task routed to {task.agent}. Execution delegated to agent module.",
        "trace_id": trace_id,
        "agent": task.agent,
        "goal": task.goal,
        "ts": _now(),
    }


def from_json(raw: str) -> AgentTask:
    """Parse a JSON string into an AgentTask."""
    data = json.loads(raw)
    return AgentTask(
        source=data.get("source", "manual"),
        agent=data.get("agent", ""),
        goal=data.get("goal", ""),
        context=data.get("context", ""),
        input_data=data.get("input_data", {}),
        approved_by=data.get("approved_by", ""),
        dry_run=bool(data.get("dry_run", False)),
        requested_command=data.get("requested_command", ""),
    )


def _cli() -> int:
    parser = argparse.ArgumentParser(description="HECATE Agent Bridge")
    parser.add_argument("--json", required=True, help="JSON task description")
    args = parser.parse_args()

    try:
        task = from_json(args.json)
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": f"Invalid JSON: {exc}"}, indent=2))
        return 1

    ok, err = validate_task(task)
    if not ok:
        print(json.dumps({"ok": False, "error": err}, indent=2))
        return 1

    result = route_task(task)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(_cli())
