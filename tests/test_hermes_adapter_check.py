from unittest.mock import patch

from hecate import hermes_adapter_check
from hecate.hermes_adapter import HermesResult


def _make_emit_capture(monkeypatch):
    captured = []
    monkeypatch.setattr(hermes_adapter_check, "emit", lambda findings, bus_path=None: captured.extend(findings))
    return captured


def test_check_writes_ok_finding(monkeypatch):
    captured = _make_emit_capture(monkeypatch)
    with patch("hecate.hermes_adapter_check.status") as mock_status:
        mock_status.return_value = HermesResult(ok=True, stdout="Hermes Agent v0.15.1")
        assert hermes_adapter_check.main() == 0
    assert len(captured) == 1
    assert captured[0].sensor == "hermes_adapter"
    assert captured[0].severity == "info"
    assert "Hermes Agent" in captured[0].evidence


def test_check_writes_failed_finding(monkeypatch):
    captured = _make_emit_capture(monkeypatch)
    with patch("hecate.hermes_adapter_check.status") as mock_status:
        mock_status.return_value = HermesResult(ok=False, returncode=1, stderr="connection refused")
        assert hermes_adapter_check.main() == 1
    assert len(captured) == 1
    assert captured[0].severity == "hoch"
    assert "connection refused" in captured[0].evidence


def test_check_catches_exception_and_writes_finding(monkeypatch):
    captured = _make_emit_capture(monkeypatch)
    with patch("hecate.hermes_adapter_check.status") as mock_status:
        mock_status.side_effect = TimeoutError("hermes timeout")
        assert hermes_adapter_check.main() == 1
    assert len(captured) == 1
    assert captured[0].severity == "hoch"
    assert "TimeoutError" in captured[0].evidence
