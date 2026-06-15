#!/usr/bin/env python3
"""hecate.claude_adapter — Adapter between Claude Code sessions and HECATE Agent Bridge.

Claude Code is session-based. This adapter lets a Claude Code session delegate
long-running or risky tasks to HECATE agents, where they are persisted,
governed, and logged.

Usage:
  python3 -m hecate.claude_adapter \
      --agent operator \
      --goal "check tmux and disk state" \
      [--approved-by maurice] \
      [--dry-run]

Claude Code rule:
  "When a task is long-running, repetitive, or risky, delegate it to HECATE
   via hecate/claude_adapter instead of running it directly in the session."
"""
from __future__ import annotations

import argparse
import json
import sys

from hecate.agent_bridge import AgentTask, route_task, validate_task


CLAUDE_DEFAULT_AGENT = "mac_builder"


def normalize(
    agent: str,
    goal: str,
    context: str = "",
    approved_by: str = "",
    dry_run: bool = False,
    requested_command: str = "",
) -> AgentTask:
    """Normalize Claude Code input into a HECATE AgentTask."""
    return AgentTask(
        source="claude",
        agent=agent or CLAUDE_DEFAULT_AGENT,
        goal=goal,
        context=context or "delegated from Claude Code session",
        approved_by=approved_by,
        dry_run=dry_run,
        requested_command=requested_command,
    )


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Claude Code to HECATE Adapter")
    parser.add_argument("--agent", default="mac_builder", help="Target HECATE agent")
    parser.add_argument("--goal", default="", help="Task goal (required unless --json is used)")
    parser.add_argument("--context", default="", help="Additional context")
    parser.add_argument("--approved-by", default="", help="Who approved the task")
    parser.add_argument("--requested-command", default="", help="Specific command if any")
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
            source="claude",
            agent=data.get("agent", CLAUDE_DEFAULT_AGENT),
            goal=data.get("goal", ""),
            context=data.get("context", ""),
            input_data=data.get("input_data", {}),
            approved_by=data.get("approved_by", ""),
            dry_run=bool(data.get("dry_run", False)),
            requested_command=data.get("requested_command", ""),
        )
    else:
        task = normalize(
            agent=args.agent,
            goal=args.goal,
            context=args.context,
            approved_by=args.approved_by,
            dry_run=args.dry_run,
            requested_command=args.requested_command,
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
