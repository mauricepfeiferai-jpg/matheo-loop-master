from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hecate.model_route_gate import ModelRouteGate, RouteDecision
from hecate.reasoning_router import ReasoningRouter, TaskType


def test_decide_local_when_ollama_alive(tmp_path, monkeypatch):
    router = MagicMock(spec=ReasoningRouter)
    router.is_ollama_alive.return_value = True
    router.models = {TaskType.REASON: MagicMock(name="qwen2.5:1.5b")}

    gate = ModelRouteGate(router=router, db_path=tmp_path / "route.db", cloud_enabled=False)
    d = gate.decide("reason")
    assert d.provider == "ollama"
    assert d.reason == "local_default"


def test_decide_cloud_when_ollama_dead(tmp_path, monkeypatch):
    router = MagicMock(spec=ReasoningRouter)
    router.is_ollama_alive.return_value = False
    router.models = {TaskType.REASON: MagicMock(name="qwen2.5:1.5b")}

    monkeypatch.setattr("hecate.model_route_gate.load_config", lambda: {})
    gate = ModelRouteGate(router=router, db_path=tmp_path / "route.db", cloud_enabled=True)
    d = gate.decide("reason")
    assert d.provider == "claude"
    assert d.reason == "ollama_unavailable"


def test_cloud_required_tasks_go_cloud(tmp_path, monkeypatch):
    router = MagicMock(spec=ReasoningRouter)
    router.is_ollama_alive.return_value = True
    router.models = {TaskType.VISION: MagicMock(name="qwen2.5-coder:7b")}

    monkeypatch.setattr("hecate.model_route_gate.load_config", lambda: {})
    gate = ModelRouteGate(router=router, db_path=tmp_path / "route.db", cloud_enabled=False)
    d = gate.decide("vision")
    assert d.provider == "claude"
    assert d.reason == "cloud_required_task"


def test_force_local_overrides_cloud_required(tmp_path):
    router = MagicMock(spec=ReasoningRouter)
    router.is_ollama_alive.return_value = True
    router.models = {TaskType.VISION: MagicMock(name="qwen2.5-coder:7b")}

    gate = ModelRouteGate(router=router, db_path=tmp_path / "route.db", cloud_enabled=False)
    d = gate.decide("vision", force_local=True)
    assert d.provider == "ollama"
    assert d.reason == "force_local"


def test_failures_exceeded_triggers_cloud_fallback(tmp_path, monkeypatch):
    router = MagicMock(spec=ReasoningRouter)
    router.is_ollama_alive.return_value = True
    router.models = {TaskType.REASON: MagicMock(name="qwen2.5:1.5b")}

    monkeypatch.setattr("hecate.model_route_gate.load_config", lambda: {})
    gate = ModelRouteGate(router=router, db_path=tmp_path / "route.db", cloud_enabled=True)
    # 3 fehlgeschlagene Laeufe loggen
    for _ in range(3):
        gate.log_attempt(
            task_type="reason",
            decision=RouteDecision(model="qwen2.5:1.5b", provider="ollama", reason="x", estimated_cost_usd=0),
            success=False,
            latency_ms=100,
        )
    d = gate.decide("reason")
    assert d.provider == "claude"
    assert d.reason == "local_failures_exceeded"


def test_log_and_stats(tmp_path):
    router = MagicMock(spec=ReasoningRouter)
    router.is_ollama_alive.return_value = True
    router.models = {TaskType.REASON: MagicMock(name="qwen2.5:1.5b")}

    gate = ModelRouteGate(router=router, db_path=tmp_path / "route.db")
    gate.log_attempt(
        task_type="reason",
        decision=RouteDecision(model="qwen2.5:1.5b", provider="ollama", reason="x", estimated_cost_usd=0),
        success=True,
        latency_ms=250,
        prompt_len=100,
        response_len=50,
    )
    stats = gate.stats()
    assert stats["total"] == 1
    assert stats["local"] == 1
    assert stats["success_rate"] == 1.0


def test_run_success_logs_and_returns_response(tmp_path):
    router = MagicMock(spec=ReasoningRouter)
    router.is_ollama_alive.return_value = True
    router.models = {TaskType.REASON: MagicMock(name="qwen2.5:1.5b")}
    router.models[TaskType.REASON].name = "qwen2.5:1.5b"
    router.generate.return_value = "local model response"

    gate = ModelRouteGate(router=router, db_path=tmp_path / "route.db")
    result = gate.run("reason", "hello")
    assert result["success"] is True
    assert result["response"] == "local model response"
    assert result["decision"]["provider"] == "ollama"


def test_run_failure_logs_and_returns_error(tmp_path):
    router = MagicMock(spec=ReasoningRouter)
    router.is_ollama_alive.return_value = True
    router.models = {TaskType.REASON: MagicMock(name="qwen2.5:1.5b")}
    router.models[TaskType.REASON].name = "qwen2.5:1.5b"
    from hecate.reasoning_router import ReasoningError
    router.generate.side_effect = ReasoningError("timeout")

    gate = ModelRouteGate(router=router, db_path=tmp_path / "route.db")
    result = gate.run("reason", "hello")
    assert result["success"] is False
    assert "timeout" in result["error"]
    stats = gate.stats()
    assert stats["success_rate"] == 0.0
