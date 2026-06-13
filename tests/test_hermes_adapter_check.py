import json
from unittest.mock import patch

from hecate import hermes_adapter_check
from hecate.hermes_adapter import HermesResult


def test_check_writes_ok_finding(tmp_path, monkeypatch):
    bus = tmp_path / "findings.jsonl"
    monkeypatch.setattr(hermes_adapter_check, "BUS", bus)
    with patch("hecate.hermes_adapter_check.status") as mock_status:
        mock_status.return_value = HermesResult(ok=True, stdout="Hermes Agent v0.15.1")
        assert hermes_adapter_check.main() == 0
    lines = bus.read_text().strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["sensor"] == "hermes_adapter"
    assert rec["severity"] == "info"
    assert "Hermes Agent" in rec["evidence"]


def test_check_writes_failed_finding(tmp_path, monkeypatch):
    bus = tmp_path / "findings.jsonl"
    monkeypatch.setattr(hermes_adapter_check, "BUS", bus)
    with patch("hecate.hermes_adapter_check.status") as mock_status:
        mock_status.return_value = HermesResult(ok=False, returncode=1, stderr="connection refused")
        assert hermes_adapter_check.main() == 1
    rec = json.loads(bus.read_text().strip().splitlines()[0])
    assert rec["severity"] == "hoch"
    assert "connection refused" in rec["evidence"]
