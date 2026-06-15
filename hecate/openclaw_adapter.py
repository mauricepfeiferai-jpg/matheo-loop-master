#!/usr/bin/env python3
"""hecate.openclaw_adapter — Adapter between OpenClaw and HECATE Agent Bridge.

OpenClaw commands/tasks are normalized into HECATE AgentTask format and routed
through agent_bridge. This prevents OpenClaw from executing destructive actions
without Policy Guard approval.

Usage:
  python3 -m hecate.openclaw_adapter \
      --agent operator \
      --goal "inspect system state" \
      --command "tmux list-sessions" \
      [--approved-by maurice] \
      [--dry-run]

OpenClaw integration rule:
  "Every OpenClaw action that touches files, shell, services, cron, network, or
   secrets must pass through hecate/openclaw_adapter. Direct execution is blocked."
"""
from __future__ import annotations

import argparse
import json
import sys

from hecate.agent_bridge import AgentTask, route_task, validate_task


OPENSCLAW_DEFAULT_AGENT = "hetzner_operator"


def normalize(
    agent: str,
    goal: str,
    command: str = "",
    context: str = "",
    approved_by: str = "",
    dry_run: bool = False,
) -> AgentTask:
    """Normalize OpenClaw input into a HECATE AgentTask."""
    return AgentTask(
        source="openclaw",
        agent=agent or OPENSCLAW_DEFAULT_AGENT,
        goal=goal,
        context=context or f"requested_command={command}",
        approved_by=approved_by,
        dry_run=dry_run,
        requested_command=command,
    )


def _cli() -> int:
    parser = argparse.ArgumentParser(description="OpenClaw to HECATE Adapter")
    parser.add_argument("--agent", default="hetzner_operator", help="Target HECATE agent")
    parser.add_argument("--goal", default="", help="Task goal (required unless --json is used)")
    parser.add_argument("--command", default="", help="Specific OpenClaw command being requested")
    parser.add_argument("--context", default="", help="Additional context")
    parser.add_argument("--approved-by", default="", help="Who approved the task")
    parser.add_argument("--dry-run", action="store_true", help="Validate and route without executing")
    parser.add_argument("--json", default="", help="Receive full task as JSON instead of CLI args")
    args = parser.parse_args()

    if not args.json and not args.goal:
        print(json.dumps({"ok": False, "error": "--goal is required unless --json is used"}, indent=2))
        return 1

    if args.json:
        try:
            data = json.loads(args.json)
        except json.JSONDecodeError as exc:
            print(json.dumps({"ok": False, "error": f"Invalid JSON: {exc}"}, indent=2))
            return 1
        task = AgentTask(
            source="openclaw",
            agent=data.get("agent", OPENSCLAW_DEFAULT_AGENT),
            goal=data.get("goal", ""),
            context=data.get("context", ""),
            input_data=data.get("input_data", {}),
            approved_by=data.get("approved_by", ""),
            dry_run=bool(data.get("dry_run", False)),
            requested_command=data.get("requested_command", data.get("command", "")),
        )
    else:
        task = normalize(
            agent=args.agent,
            goal=args.goal,
            command=args.command,
            context=args.context,
            approved_by=args.approved_by,
            dry_run=args.dry_run,
        )

    ok, err = validate_task(task)
    if not ok:
        print(json.dumps({"ok": False, "error": err}, indent=2))
        return 1

    result = route_task(task)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(_cli())
