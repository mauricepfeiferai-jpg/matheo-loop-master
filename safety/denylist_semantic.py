#!/usr/bin/env python3
"""Semantic Deny-List — erweitert Regex mit Begriffs-Analyse.

Schließt Lücke #10: Deny-List Regex-basiert, semantische Bypasses möglich.
"""
import re
from pathlib import Path

# Hard deny patterns (Regex)
HARD_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"mkfs\.",
    r"dd\s+if=.*of=/dev/",
    r"git\s+.*--force",
    r"git\s+.*-f",
    r"apt\s+(remove|purge|autoremove)",
    r"chmod\s+777\s+/",
]

# Semantic categories
SEMANTIC_DENY = {
    "filesystem_destructive": ["rm", "rmdir", "unlink", "shred", "wipe"],
    "disk_format": ["mkfs", "fdisk", "parted", "format"],
    "raw_disk_write": ["dd", "pv", "cat", "cp"],
    "service_kill": ["kill", "pkill", "killall", "systemctl stop"],
    "privilege_escalation": ["chmod 777", "chown root", "sudo -i", "su -"],
    "network_risk": ["iptables -F", "ufw disable", "firewall"],
    "secret_exposure": ["cat.*env", "echo.*api_key", "print.*token"],
}


def is_denied(cmd: str) -> tuple[bool, str]:
    """Prüft ob ein Befehl denied ist."""
    cmd_lower = cmd.lower()

    # 1. Hard patterns
    for pat in HARD_PATTERNS:
        if re.search(pat, cmd_lower):
            return True, f"Hard deny: regex matched {pat}"

    # 2. Semantic analysis
    for category, keywords in SEMANTIC_DENY.items():
        for kw in keywords:
            if kw in cmd_lower:
                # Context check: Is it targeting a sensitive path?
                sensitive_paths = ["/", "/etc", "/var", "/root", "/home"]
                for sp in sensitive_paths:
                    if sp in cmd_lower:
                        return True, f"Semantic deny: {category} targeting {sp}"

    return False, ""


def audit_cmd(cmd: str) -> dict:
    """Detaillierte Audit-Info."""
    denied, reason = is_denied(cmd)
    return {
        "cmd": cmd,
        "denied": denied,
        "reason": reason,
        "risk_level": "CRITICAL" if denied else "LOW",
    }


if __name__ == "__main__":
    import sys
    tests = [
        "rm -rf /tmp/old",
        "rm -rf /etc",
        "dd if=/dev/zero of=/dev/sda",
        "git push origin main",
        "echo hello",
    ]
    for t in tests:
        r = audit_cmd(t)
        print(f"{'❌' if r['denied'] else '✅'} {t} — {r['reason']}")
