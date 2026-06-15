"""Tests for HECATE agent contract files.

Ensures all 8 agent contracts exist, are parseable, and contain required sections.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

AGENTS_DIR = Path(__file__).parent.parent / "agents"

REQUIRED_AGENT_NAMES = [
    "hetzner_operator",
    "hetzner_sensor",
    "hetzner_digest",
    "hetzner_policy_guard",
    "hetzner_scout",
    "mac_builder",
    "mac_reviewer",
    "mac_strategist",
]

REQUIRED_SECTIONS = [
    "## Identity",
    "## Role",
    "## Job",
    "## Default Autonomy",
    "## Model Strategy",
    "## Safety Boundaries",
    "## Failure Modes",
    "## Learning Ledger Fields",
]


@pytest.fixture(params=REQUIRED_AGENT_NAMES)
def agent_name(request):
    return request.param


def test_agent_contract_file_exists(agent_name):
    path = AGENTS_DIR / f"{agent_name}.md"
    assert path.exists(), f"Contract file missing: {path}"


def test_agent_contract_has_required_sections(agent_name):
    path = AGENTS_DIR / f"{agent_name}.md"
    text = path.read_text(encoding="utf-8")
    for section in REQUIRED_SECTIONS:
        assert section in text, f"{agent_name} missing section: {section}"


def test_agent_contract_has_no_forbidden_autonomy_claims(agent_name):
    path = AGENTS_DIR / f"{agent_name}.md"
    text = path.read_text(encoding="utf-8").lower()
    forbidden = [
        "unlimited autonomy",
        "full access",
        "no restrictions",
        "execute without approval",
    ]
    for phrase in forbidden:
        assert phrase not in text, f"{agent_name} contains forbidden autonomy phrase: {phrase}"


def test_policy_guard_contract_blocks_critical_actions():
    path = AGENTS_DIR / "hetzner_policy_guard.md"
    text = path.read_text(encoding="utf-8").lower()
    required_blocks = [
        "secrets",
        "rm",
        "systemctl restart",
        "cron",
        "telegram",
        "live trading",
        "legal",
        "curl | bash",
    ]
    for block in required_blocks:
        assert block in text, f"Policy Guard missing block for: {block}"


def test_scout_contract_is_read_only_proposal_only():
    path = AGENTS_DIR / "hetzner_scout.md"
    text = path.read_text(encoding="utf-8").lower()
    assert "proposal-only" in text or "proposal only" in text
    assert "forbidden" in text
    assert "install" in text or "installing" in text
    assert "clone" in text or "cloning" in text
    assert "cron" in text


def test_builder_contract_forbids_system_paths():
    path = AGENTS_DIR / "mac_builder.md"
    text = path.read_text(encoding="utf-8").lower()
    for forbidden in ["/etc", "systemd", "cron", "telegram", "live trading", "legal"]:
        assert forbidden in text, f"mac_builder missing forbidden item: {forbidden}"


def test_reviewer_contract_required_before_promotion():
    path = AGENTS_DIR / "mac_reviewer.md"
    text = path.read_text(encoding="utf-8").lower()
    assert "green" in text and "yellow" in text and "red" in text
    assert "before promotion" in text or "before any promotion" in text


def test_strategist_contract_is_proposal_only():
    path = AGENTS_DIR / "mac_strategist.md"
    text = path.read_text(encoding="utf-8").lower()
    assert "proposal-only" in text or "proposal only" in text
    assert "execution" in text and "never automatic" in text
