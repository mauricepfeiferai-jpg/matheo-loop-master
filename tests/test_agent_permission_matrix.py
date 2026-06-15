"""Tests for HECATE agent permission matrix.

Ensures default DENY, explicit ALLOW, and required forbidden permissions.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

GOVERNANCE_DIR = Path(__file__).parent.parent / "governance"
MATRIX_PATH = GOVERNANCE_DIR / "agent_permission_matrix.yaml"

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

DANGEROUS_PERMISSIONS = [
    "secrets_access",
    "legal_mutation",
    "trading_mutation",
    "production_restart",
    "systemd_write",
    "cron_write",
    "telegram_send",
    "shell_write",
]


@pytest.fixture
def matrix():
    return yaml.safe_load(MATRIX_PATH.read_text(encoding="utf-8"))


def test_matrix_file_exists():
    assert MATRIX_PATH.exists()


def test_all_permissions_defined(matrix):
    keys = [p["key"] for p in matrix["permissions"]]
    for dp in DANGEROUS_PERMISSIONS:
        assert dp in keys, f"Dangerous permission not defined: {dp}"


def test_all_agents_present(matrix):
    assert set(matrix["agents"].keys()) == set(AGENTS)


def test_default_deny_for_dangerous_permissions(matrix):
    for agent in AGENTS:
        for perm in DANGEROUS_PERMISSIONS:
            value = matrix["agents"][agent].get(perm)
            assert value in ("DENY", "ALLOW"), f"{agent}.{perm} must be DENY or ALLOW"
            assert value == "DENY", f"{agent}.{perm} must default DENY, got {value}"


def test_operator_is_read_only(matrix):
    op = matrix["agents"]["hetzner_operator"]
    assert op["shell_readonly"] == "ALLOW"
    assert op["shell_write"] == "DENY"
    assert op["systemd_write"] == "DENY"
    assert op["cron_write"] == "DENY"
    assert op["write_files"] == "DENY"


def test_policy_guard_has_limited_scope(matrix):
    pg = matrix["agents"]["hetzner_policy_guard"]
    assert pg["shell_readonly"] == "DENY"
    assert pg["shell_write"] == "DENY"
    assert pg["telegram_send"] == "DENY"


def test_builder_can_write_and_test_in_workspace(matrix):
    builder = matrix["agents"]["mac_builder"]
    assert builder["write_files"] == "ALLOW"
    assert builder["run_tests"] == "ALLOW"
    assert builder["shell_write"] == "DENY"
    assert builder["systemd_write"] == "DENY"


def test_scout_network_allowed_but_no_system_mutation(matrix):
    scout = matrix["agents"]["hetzner_scout"]
    assert scout["network_access"] == "ALLOW"
    assert scout["shell_write"] == "DENY"
    assert scout["cron_write"] == "DENY"
    assert scout["telegram_send"] == "DENY"


def test_emergency_override_requires_reason(matrix):
    eo = matrix["emergency_override"]
    assert eo["requires_reason"] is True
    assert eo["logs_as"] == "safety_block"


def test_archivist_is_read_analyst_with_report_write(matrix):
    a = matrix["agents"]["hetzner_archivist"]
    assert a["read_files"] == "ALLOW"
    assert a["write_files"] == "ALLOW"
    assert a["shell_write"] == "DENY"
    assert a["telegram_send"] == "DENY"


def test_security_scanner_is_metadata_only(matrix):
    s = matrix["agents"]["hetzner_security_scanner"]
    assert s["shell_readonly"] == "ALLOW"
    assert s["shell_write"] == "DENY"
    assert s["secrets_access"] == "DENY"
    assert s["systemd_write"] == "DENY"


def test_performance_profiler_reads_metrics(matrix):
    p = matrix["agents"]["hetzner_performance_profiler"]
    assert p["shell_readonly"] == "ALLOW"
    assert p["shell_write"] == "DENY"
    assert p["production_restart"] == "DENY"


def test_cost_guard_and_backup_checker_cannot_mutate(matrix):
    for name in ("hetzner_cost_guard", "hetzner_backup_checker"):
        agent = matrix["agents"][name]
        assert agent["shell_write"] == "DENY"
        assert agent["systemd_write"] == "DENY"
        assert agent["telegram_send"] == "DENY"
