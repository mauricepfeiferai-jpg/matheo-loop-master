"""Tests for HECATE Agent Bridge.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hecate.agent_bridge import AgentTask, from_json, route_task, validate_task


@pytest.fixture
def mock_ledger(monkeypatch):
    mock = MagicMock()
    mock.return_value.record.return_value = "trace-123"
    monkeypatch.setattr("hecate.agent_bridge.LearningLedger", mock)
    return mock


def test_valid_task():
    task = AgentTask(
        source="manual",
        agent="hetzner_operator",
        goal="check system state",
        dry_run=True,
    )
    ok, err = validate_task(task)
    assert ok
    assert err == ""


def test_unknown_agent_invalid():
    task = AgentTask(
        source="manual",
        agent="invalid_agent",
        goal="do something",
        dry_run=True,
    )
    ok, err = validate_task(task)
    assert not ok
    assert "Unknown agent" in err


def test_empty_goal_invalid():
    task = AgentTask(
        source="manual",
        agent="hetzner_operator",
        goal="",
        dry_run=True,
    )
    ok, err = validate_task(task)
    assert not ok
    assert "goal is required" in err


def test_from_json_parses_task():
    raw = '{"source": "hermes", "agent": "hetzner_operator", "goal": "check disk", "approved_by": "maurice"}'
    task = from_json(raw)
    assert task.source == "hermes"
    assert task.agent == "hetzner_operator"
    assert task.goal == "check disk"
    assert task.approved_by == "maurice"


def test_route_task_dry_run(mock_ledger):
    task = AgentTask(
        source="manual",
        agent="hetzner_operator",
        goal="check tmux and disk state",
        requested_command="tmux list-sessions",
        dry_run=True,
    )
    result = route_task(task)
    assert result["ok"] is True
    assert result["verdict"]["verdict"] == "ALLOW"
    assert result["trace_id"] == "trace-123"


def test_route_task_denied_without_approval(mock_ledger):
    task = AgentTask(
        source="manual",
        agent="hetzner_operator",
        goal="restart service",
        requested_command="systemctl restart codex-bridge",
        dry_run=False,
    )
    result = route_task(task)
    assert result["ok"] is False
    assert result["verdict"]["verdict"] == "REQUIRE_MAURICE_GO"
    assert "Maurice GO" in result["message"]


def test_route_task_denied_forbidden(mock_ledger):
    task = AgentTask(
        source="manual",
        agent="hetzner_operator",
        goal="delete project",
        requested_command="rm -rf /root/projects/loop-master",
        dry_run=False,
    )
    result = route_task(task)
    assert result["ok"] is False
    assert result["verdict"]["verdict"] == "DENY"


def test_route_task_approved_mutation_allowed(mock_ledger):
    task = AgentTask(
        source="manual",
        agent="hetzner_operator",
        goal="restart codex-bridge",
        requested_command="systemctl restart codex-bridge",
        approved_by="maurice",
        dry_run=False,
    )
    result = route_task(task)
    # Even with approval, systemctl still requires GO per policy, but approval is present.
    # The bridge allows routing; execution is still delegated to the agent module.
    assert result["ok"] is True
    assert result["trace_id"] == "trace-123"
