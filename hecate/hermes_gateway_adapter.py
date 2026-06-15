#!/usr/bin/env python3
"""hecate.hermes_gateway_adapter — Adapter between Hermes and HECATE Agent Bridge.

Hermes profiles send tasks to this adapter. It normalizes them into the
HECATE AgentTask format and routes them through agent_bridge.

Usage:
  python3 -m hecate.hermes_gateway_adapter \
      --profile hecate-ops \
      --agent operator \
      --goal "check tmux and disk state" \
      [--approved-by maurice] \
      [--dry-run]

Hermes SOUL.md rule for every HECATE profile:
  "Route every action through hecate/hermes_gateway_adapter. Never execute
   shell commands, systemd changes, cron edits, or Telegram sends directly."
"""
from __future__ import annotations

import argparse
import json
import sys

from hecate.agent_bridge import AgentTask, route_task, validate_task


HERMES_PROFILE_TO_AGENT = {
    "hecate-chief": "hetzner_operator",
    "hecate-ops": "hetzner_operator",
    "hecate-research": "hetzner_scout",
    "hecate-content": "hetzner_digest",
}


def normalize(
    profile: str,
    agent: str | None,
    goal: str,
    context: str = "",
    approved_by: str = "",
    dry_run: bool = False,
    requested_command: str = "",
) -> AgentTask:
    """Normalize Hermes input into a HECATE AgentTask."""
    resolved_agent = agent or HERMES_PROFILE_TO_AGENT.get(profile, "hetzner_operator")
    return AgentTask(
        source="hermes",
        agent=resolved_agent,
        goal=goal,
        context=f"profile={profile}; {context}" if context else f"profile={profile}",
        approved_by=approved_by,
        dry_run=dry_run,
        requested_command=requested_command,
    )


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Hermes to HECATE Adapter")
    parser.add_argument("--profile", default="hecate-ops", help="Hermes profile name")
    parser.add_argument("--agent", default=None, help="Override HECATE agent")
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
            source="hermes",
            agent=data.get("agent", HERMES_PROFILE_TO_AGENT.get(data.get("profile", ""), "hetzner_operator")),
            goal=data.get("goal", ""),
            context=data.get("context", ""),
            input_data=data.get("input_data", {}),
            approved_by=data.get("approved_by", ""),
            dry_run=bool(data.get("dry_run", False)),
            requested_command=data.get("requested_command", ""),
        )
    else:
        task = normalize(
            profile=args.profile,
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
