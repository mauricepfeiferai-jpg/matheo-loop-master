import json
from pathlib import Path
from unittest.mock import patch

from hecate.decision_card_loop import _build_card, _map_category, _map_risk_level


def test_map_category_known_sensors():
    assert _map_category("secret_scan") == "RISK"
    assert _map_category("config_drift") == "INTEGRATE_INTO_HECATE"
    assert _map_category("disk_trend") == "DELETE_CANDIDATE"
    assert _map_category("unknown") == "NEEDS_HUMAN_CONTEXT"


def test_map_risk_level_krit_is_l5():
    assert _map_risk_level("secret_scan", "krit") == "L5"
    assert _map_risk_level("disk_trend", "hoch") == "L4"


def test_build_card_has_required_fields():
    items = [
        {"severity": "hoch", "sensor": "config_drift", "subject": "ollama.service",
         "evidence": "OLLAMA_HOST conflict", "suggested_fix": "Verlierer-Drop-in bereinigen"},
    ]
    card = _build_card("config_drift", items)
    assert card.category == "INTEGRATE_INTO_HECATE"
    assert card.risk_level in ("L4", "L5")
    assert "ollama.service" in card.evidence
    assert card.option_a
    assert card.option_b
    assert card.option_c


def test_run_creates_digest(tmp_path, monkeypatch):
    monkeypatch.setattr("hecate.decision_card_loop.DECISION_DIR", tmp_path / "decision_cards")
    monkeypatch.setattr("hecate.decision_card_loop.REPORT_DIR", tmp_path / "reports")
    monkeypatch.setattr("hecate.decision_card_loop.QUEUE_PATH", tmp_path / "queue.jsonl")
    monkeypatch.setattr("hecate.decision_card_loop.BUS", tmp_path / "findings.jsonl")
    (tmp_path / "findings.jsonl").write_text(
        json.dumps({"severity": "hoch", "sensor": "secret_scan", "subject": "token leak",
                    "evidence": "plain text", "suggested_fix": "rotate"}) + "\n"
    )
    with patch("hecate.decision_card_loop.LEDGER") as mock_ledger:
        mock_ledger.start.return_value = "r1"
        from hecate import decision_card_loop as dcl
        result = dcl.run()

    assert result["cards_created"] >= 1
    assert (tmp_path / "reports" / "decision_digest_2026-06-13.md").exists() or list((tmp_path / "reports").glob("decision_digest_*.md"))
