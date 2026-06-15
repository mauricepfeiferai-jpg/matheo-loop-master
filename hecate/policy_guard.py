#!/usr/bin/env python3
"""hecate.policy_guard — Central safety gate for all agent gateways.

Evaluates proposed actions from Hermes, OpenClaw, Claude Code, or any other
entrypoint and returns ALLOW / DENY / REQUIRE_MAURICE_GO.

Rules:
- Deterministic, rules-first.
- No cloud model calls.
- Loads agent permission matrix from governance/agent_permission_matrix.yaml.
- Fails closed: uncertain -> REQUIRE_MAURICE_GO or DENY.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml

VERDICT = Literal["ALLOW", "DENY", "REQUIRE_MAURICE_GO"]

GOVERNANCE_DIR = Path(__file__).parent.parent / "governance"
MATRIX_PATH = GOVERNANCE_DIR / "agent_permission_matrix.yaml"

FORBIDDEN_PATTERNS = [
    (r"\brm\s+-rf\b", "recursive force deletion"),
    (r"\brm\s+-r\b", "recursive deletion"),
    (r"\bgit\s+clean\s+-fd\b", "git clean"),
    (r"\bcurl\s+.*\|\s*bash", "curl pipe bash"),
    (r"\bwget\s+.*\|\s*bash", "wget pipe bash"),
    (r"\breboot\b", "reboot"),
    (r"\bshutdown\b", "shutdown"),
    (r"\bkill\s+-9\b", "force kill"),
]

SENSITIVE_PATHS = [
    "/root/.secrets",
    "/root/.ssh",
    "/etc",
    "/root/projects/legal",
]

READONLY_ALLOWLIST = [
    r"^tmux\s+list",
    r"^df\s+-h",
    r"^free\s+-h",
    r"^uptime",
    r"^git\s+(status|diff|log|show|branch)",
    r"^docker\s+ps",
    r"^docker\s+stats\s+--no-stream",
    r"^systemctl\s+status\s+\S+",
    r"^crontab\s+-l",
    r"^ls\s+-la\s+/etc/cron",
    r"^journalctl\s+-n\s+\d+",
    r"^python3\s+-m\s+pytest",
    r"^python3\s+-m\s+hecate\.(agent_smoke|hermes_gateway_adapter|openclaw_adapter|claude_adapter)",
]


def load_permission_matrix() -> dict:
    """Load permission matrix from YAML."""
    if not MATRIX_PATH.exists():
        return {}
    return yaml.safe_load(MATRIX_PATH.read_text(encoding="utf-8"))


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def is_forbidden(command: str) -> tuple[bool, str]:
    """Check if command matches a forbidden destructive pattern."""
    cmd = command.lower()
    for pattern, reason in FORBIDDEN_PATTERNS:
        if re.search(pattern, cmd):
            return True, reason
    return False, ""


def requires_go(command: str, path: str | None = None) -> tuple[bool, str]:
    """Check if command requires explicit Maurice GO."""
    forbidden, reason = is_forbidden(command)
    if forbidden:
        return True, reason

    target = f"{command} {path or ''}".lower()

    if any(p in target for p in SENSITIVE_PATHS):
        return True, "touches sensitive path"

    if ".env" in target.split() or any(target.endswith(ext) for ext in [".env", ".key", ".pem"]):
        return True, "potential secret access"

    if re.search(r"\bsystemctl\s+(restart|stop|start|enable|disable)\b|\bservice\s+\S+\s+(restart|stop|start)\b", command, re.IGNORECASE):
        return True, "system/service mutation"

    if re.search(r"\bcrontab\b|/etc/cron", command, re.IGNORECASE):
        return True, "cron mutation"

    if re.search(r"\bcurl\s+.*\|\s*bash|\bwget\s+.*\|\s*bash", command, re.IGNORECASE):
        return True, "pipe to shell"

    return False, ""


def is_readonly_allowed(command: str) -> bool:
    """Check if command is on the read-only allowlist."""
    return any(re.match(p, command.strip(), re.IGNORECASE) for p in READONLY_ALLOWLIST)


def evaluate(
    command: str,
    agent: str,
    context: str = "",
    permission_matrix: dict | None = None,
) -> dict:
    """Evaluate a proposed action and return a verdict dictionary.

    Returns:
        {
            "verdict": "ALLOW" | "DENY" | "REQUIRE_MAURICE_GO",
            "reason": str,
            "risk_level": str,
            "agent": str,
        }
    """
    matrix = permission_matrix or load_permission_matrix()
    agents = matrix.get("agents", {})
    agent_perms = agents.get(agent, {})

    # If agent is unknown, deny.
    if not agent_perms and agent != "unknown":
        return {
            "verdict": "DENY",
            "reason": f"Unknown agent: {agent}",
            "risk_level": "P0",
            "agent": agent,
        }

    forbidden, reason = is_forbidden(command)
    if forbidden:
        return {
            "verdict": "DENY",
            "reason": f"Forbidden: {reason}",
            "risk_level": "P0",
            "agent": agent,
        }

    needs_go, go_reason = requires_go(command)
    if needs_go:
        return {
            "verdict": "REQUIRE_MAURICE_GO",
            "reason": f"Requires GO: {go_reason}",
            "risk_level": "P1",
            "agent": agent,
        }

    # Check permission matrix for shell_readonly / shell_write.
    is_mutating = any(op in command.lower() for op in [">", "|", "rm", "mv", "cp", "touch", "mkdir", "chmod", "chown"])
    if is_mutating and agent_perms.get("shell_write") != "ALLOW":
        return {
            "verdict": "REQUIRE_MAURICE_GO",
            "reason": "Mutating shell command not pre-approved for agent",
            "risk_level": "P2",
            "agent": agent,
        }

    if is_readonly_allowed(command):
        return {
            "verdict": "ALLOW",
            "reason": "Recognized safe read-only command",
            "risk_level": "P4",
            "agent": agent,
        }

    # Unknown command -> require GO (fail closed).
    return {
        "verdict": "REQUIRE_MAURICE_GO",
        "reason": "Unclassified command",
        "risk_level": "P2",
        "agent": agent,
    }


def check_permission(agent: str, permission: str, matrix: dict | None = None) -> bool:
    """Check if agent has a specific permission ALLOWed."""
    mat = matrix or load_permission_matrix()
    agents = mat.get("agents", {})
    return agents.get(agent, {}).get(permission) == "ALLOW"
