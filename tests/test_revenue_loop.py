import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from hecate import revenue_loop as rl


def test_system_health_pauses_on_critical_findings(tmp_path, monkeypatch):
    bus = tmp_path / "findings.jsonl"
    bus.write_text(
        json.dumps({"severity": "krit", "sensor": "x", "subject": "y", "evidence": "z"}) + "\n"
    )
    result = rl._system_health_ok(bus)
    assert result[0] is False
    assert "krit" in result[1]


def test_system_health_pauses_on_many_high_findings(tmp_path, monkeypatch):
    bus = tmp_path / "findings.jsonl"
    lines = [json.dumps({"severity": "hoch", "sensor": "x", "subject": "y", "evidence": "z"}) for _ in range(5)]
    bus.write_text("\n".join(lines) + "\n")
    result = rl._system_health_ok(bus)
    assert result[0] is False
    assert "hoch" in result[1]


def test_system_health_ok_when_stable(tmp_path):
    bus = tmp_path / "findings.jsonl"
    bus.write_text(
        json.dumps({"severity": "info", "sensor": "x", "subject": "y", "evidence": "z"}) + "\n"
    )
    result = rl._system_health_ok(bus)
    assert result[0] is True


def test_collect_context_returns_profile_and_gold(tmp_path, monkeypatch):
    monkeypatch.setattr("hecate.revenue_loop.get_profile", lambda: {"style": "kurz", "language": "de"})
    monkeypatch.setattr("hecate.revenue_loop.get_decisions", lambda topic, n: [])

    fake_gold = [
        {"id": "g1", "name": "KI-Automation", "content": "Automatisierung mit lokalen Modellen", "gold_score": 0.9}
    ]
    monkeypatch.setattr("hecate.revenue_loop.query_gold", lambda topic, limit: fake_gold)

    ctx = rl._collect_context()
    assert ctx["profile"]["language"] == "de"
    assert len(ctx["gold_knowledge"]) == 1


def test_parse_json_safely_extracts_json_from_markdown():
    text = "Some text\n```json\n{\"action\": \"post\"}\n```\nmore"
    parsed = rl._parse_json_safely(text)
    assert parsed == {"action": "post"}


def test_parse_json_safely_returns_none_for_invalid():
    assert rl._parse_json_safely("no json here") is None


def test_run_creates_proposal_when_healthy(tmp_path, monkeypatch):
    bus = tmp_path / "findings.jsonl"
    bus.write_text("")
    monkeypatch.setattr("hecate.revenue_loop.BUS_PATH", bus)
    monkeypatch.setattr("hecate.revenue_loop.get_profile", lambda: {"style": "kurz", "language": "de"})
    monkeypatch.setattr("hecate.revenue_loop.get_decisions", lambda topic, n: [])
    monkeypatch.setattr("hecate.revenue_loop.query_gold", lambda topic, limit: [])

    fake_gate = MagicMock()
    fake_gate.run.return_value = {
        "success": True,
        "response": '{"action": "post on X", "channel": "X", "target_icp": "KI-Interessierte", "effort_hours": 1.0, "expected_outcome": "reach", "why_now": "Montag"}',
        "decision": {"model": "qwen2.5:1.5b", "provider": "ollama"},
        "latency_ms": 1234,
    }
    monkeypatch.setattr("hecate.revenue_loop.ModelRouteGate", lambda **kwargs: fake_gate)

    proposals_dir = tmp_path / "proposals"
    monkeypatch.setattr("hecate.revenue_loop.Path", lambda p: (proposals_dir if p == "/root/projects/loop-master/proposals" else Path(p)))

    result = rl.run()
    assert result["status"] == "created"
    assert result["proposal_id"].startswith("revenue-daily-")


def test_run_paused_on_critical(tmp_path, monkeypatch):
    bus = tmp_path / "findings.jsonl"
    bus.write_text(
        json.dumps({"severity": "krit", "sensor": "x", "subject": "y", "evidence": "z"}) + "\n"
    )
    monkeypatch.setattr("hecate.revenue_loop.BUS_PATH", bus)
    result = rl.run()
    assert result["status"] == "paused"
    assert result["proposal_id"] is None
