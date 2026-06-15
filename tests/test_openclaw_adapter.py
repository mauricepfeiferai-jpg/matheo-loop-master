"""Tests for OpenClaw to HECATE adapter.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hecate.openclaw_adapter import normalize


@pytest.fixture
def mock_ledger(monkeypatch):
    mock = MagicMock()
    mock.return_value.record.return_value = "trace-openclaw-123"
    monkeypatch.setattr("hecate.agent_bridge.LearningLedger", mock)
    return mock


def test_normalize_sets_source_openclaw():
    task = normalize(
        agent="hetzner_operator",
        goal="inspect system",
        command="tmux list-sessions",
    )
    assert task.source == "openclaw"
    assert task.agent == "hetzner_operator"
    assert "tmux list-sessions" in task.context


def test_cli_routes_openclaw_task(mock_ledger):
    with patch("sys.argv", [
        "hecate.openclaw_adapter",
        "--agent", "hetzner_operator",
        "--goal", "check system state",
        "--command", "df -h",
        "--dry-run",
    ]):
        from hecate import openclaw_adapter
        result = openclaw_adapter._cli()
        assert result == 0


def test_cli_denies_destructive_openclaw_command(mock_ledger):
    with patch("sys.argv", [
        "hecate.openclaw_adapter",
        "--agent", "hetzner_operator",
        "--goal", "clean project",
        "--command", "git clean -fd",
    ]):
        from hecate import openclaw_adapter
        result = openclaw_adapter._cli()
        assert result == 1
