"""Tests for Hermes to HECATE gateway adapter.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hecate.hermes_gateway_adapter import normalize


@pytest.fixture
def mock_ledger(monkeypatch):
    mock = MagicMock()
    mock.return_value.record.return_value = "trace-hermes-123"
    monkeypatch.setattr("hecate.agent_bridge.LearningLedger", mock)
    return mock


def test_normalize_maps_profile_to_agent():
    task = normalize(
        profile="hecate-research",
        agent=None,
        goal="scout github",
    )
    assert task.agent == "hetzner_scout"
    assert task.source == "hermes"
    assert "hecate-research" in task.context


def test_normalize_allows_agent_override():
    task = normalize(
        profile="hecate-ops",
        agent="hetzner_digest",
        goal="compress report",
    )
    assert task.agent == "hetzner_digest"


def test_cli_routes_operator_task(mock_ledger):
    with patch("sys.argv", [
        "hecate.hermes_gateway_adapter",
        "--profile", "hecate-ops",
        "--goal", "check tmux and disk state",
        "--requested-command", "tmux list-sessions",
        "--dry-run",
    ]):
        from hecate import hermes_gateway_adapter
        result = hermes_gateway_adapter._cli()
        assert result == 0


def test_cli_denies_forbidden_command(mock_ledger):
    with patch("sys.argv", [
        "hecate.hermes_gateway_adapter",
        "--profile", "hecate-ops",
        "--goal", "delete project",
        "--requested-command", "rm -rf /root/projects/loop-master",
    ]):
        from hecate import hermes_gateway_adapter
        result = hermes_gateway_adapter._cli()
        assert result == 1


def test_json_input_route(mock_ledger):
    raw = '{"source": "hermes", "profile": "hecate-ops", "agent": "hetzner_operator", "goal": "check disk", "requested_command": "df -h", "dry_run": true}'
    with patch("sys.argv", ["hecate.hermes_gateway_adapter", "--json", raw]):
        from hecate import hermes_gateway_adapter
        result = hermes_gateway_adapter._cli()
        assert result == 0
