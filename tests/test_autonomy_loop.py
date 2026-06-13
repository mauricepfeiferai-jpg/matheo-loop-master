import json
from unittest.mock import patch

from hecate.autonomy_loop import check_safety, generate_improvement, run


def test_generate_improvement_returns_proposal_structure(tmp_path, monkeypatch):
    monkeypatch.setattr("hecate.autonomy_loop.BUS", tmp_path / "findings.jsonl")
    (tmp_path / "findings.jsonl").write_text(
        json.dumps({"severity": "hoch", "sensor": "config_drift", "subject": "x",
                    "evidence": "y", "suggested_fix": "z"}) + "\n"
    )
    with patch("hecate.autonomy_loop._maybe_llm_title") as mock_title:
        mock_title.return_value = ("Bessere Config-Drift Erkennung", "Score statt Spam")
        result = generate_improvement()

    assert result["proposal_id"].startswith("hecate-autonomy")
    assert result["sensor"] == "config_drift"
    assert "test_file" in result
    assert "test_code" in result


def test_check_safety_flags_denylist():
    proposal = {"test_code": "", "module_code": "rm -rf /"}
    result = check_safety(proposal)
    assert result["ok"] is False
    assert len(result["hits"]) > 0


def test_check_safety_ok_for_safe_code():
    proposal = {"test_code": "def test_foo(): assert 1 == 1", "module_code": "x = 1 + 1"}
    result = check_safety(proposal)
    assert result["ok"] is True


def test_run_uses_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr("hecate.autonomy_loop.BUS", tmp_path / "findings.jsonl")
    monkeypatch.setattr("hecate.autonomy_loop.PROPOSALS_DIR", tmp_path / "proposals")
    monkeypatch.setattr("hecate.autonomy_loop.DECISION_DIR", tmp_path / "decision_cards")
    (tmp_path / "findings.jsonl").write_text(
        json.dumps({"severity": "hoch", "sensor": "restart_loops", "subject": "x",
                    "evidence": "y", "suggested_fix": "z"}) + "\n"
    )
    with patch("hecate.autonomy_loop._maybe_llm_title") as mock_title:
        mock_title.return_value = ("Restart Loop Fix", "Reduce restart spam")
        with patch("hecate.autonomy_loop.LEDGER") as mock_ledger:
            mock_ledger.start.return_value = "r1"
            result = run()

    assert result["ok"] is True
    assert mock_ledger.start.called
