"""Tests for Claude Code to HECATE adapter.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hecate.claude_adapter import normalize


@pytest.fixture
def mock_ledger(monkeypatch):
    mock = MagicMock()
    mock.return_value.record.return_value = "trace-claude-123"
    monkeypatch.setattr("hecate.agent_bridge.LearningLedger", mock)
    return mock


def test_normalize_defaults_to_mac_builder():
    task = normalize(
        agent="",
        goal="refactor module",
    )
    assert task.source == "claude"
    assert task.agent == "mac_builder"


def test_normalize_allows_operator_override():
    task = normalize(
        agent="hetzner_operator",
        goal="check system",
    )
    assert task.agent == "hetzner_operator"


def test_cli_routes_claude_task(mock_ledger):
    with patch("sys.argv", [
        "hecate.claude_adapter",
        "--agent", "mac_builder",
        "--goal", "refactor auth module",
        "--requested-command", "python3 -m pytest tests/",
        "--dry-run",
    ]):
        from hecate import claude_adapter
        result = claude_adapter._cli()
        assert result == 0


def test_cli_denies_risky_claude_command(mock_ledger):
    with patch("sys.argv", [
        "hecate.claude_adapter",
        "--agent", "hetzner_operator",
        "--goal", "restart service",
        "--requested-command", "systemctl restart codex-bridge",
    ]):
        from hecate import claude_adapter
        result = claude_adapter._cli()
        assert result == 1
