import json
from pathlib import Path
from unittest.mock import patch

from hecate import ollama_manager as om


def test_estimate_model_size_gb():
    assert om.estimate_model_size_gb("qwen2.5:0.5b") == 0.25
    assert om.estimate_model_size_gb("qwen2.5:1.5b") == 0.75
    assert om.estimate_model_size_gb("qwen2.5-coder:7b") == 3.5
    assert om.estimate_model_size_gb("qwen3:30b-a3b") == 15.0
    assert om.estimate_model_size_gb("unknown") == 4.0


def test_recommend_model_for_task_prefers_preferred_when_fits(monkeypatch):
    monkeypatch.setattr(om, "can_fit_model", lambda name, headroom_gb=2.0: name == "qwen2.5-coder:7b")
    assert om.recommend_model_for_task("qwen2.5-coder:7b") == "qwen2.5-coder:7b"


def test_recommend_model_for_task_falls_back_when_needed(monkeypatch):
    monkeypatch.setattr(om, "can_fit_model", lambda name, headroom_gb=2.0: name == "qwen2.5:0.5b")
    assert om.recommend_model_for_task("qwen2.5-coder:7b") == "qwen2.5:0.5b"


def test_available_memory_gb_returns_positive_on_server():
    # Auf einem echten Server sollte das funktionieren.
    mem = om.available_memory_gb()
    assert mem > 0.0


def test_prepare_for_model_unloads_others_and_recommends(tmp_path, monkeypatch):
    running = [
        om.RunningModel("qwen3:30b-a3b", 20 * 1024 * 1024 * 1024, "later"),
    ]
    monkeypatch.setattr(om, "list_running_models", lambda: running)
    monkeypatch.setattr(om, "unload_model", lambda name, timeout=60: True)
    monkeypatch.setattr(om, "available_memory_gb", lambda: 8.0)

    result = om.prepare_for_model("qwen2.5:1.5b")
    assert result["requested_model"] == "qwen2.5:1.5b"
    assert result["memory_ok"] is True
    assert result["available_gb"] == 8.0


def test_ensure_only_model_loaded_unloads_non_target(monkeypatch):
    running = [
        om.RunningModel("qwen3:30b-a3b", 20 * 1024 * 1024 * 1024, "later"),
        om.RunningModel("qwen2.5:1.5b", 1 * 1024 * 1024 * 1024, "later"),
    ]
    unloaded = []

    def fake_unload(name, timeout=60):
        unloaded.append(name)
        return True

    monkeypatch.setattr(om, "list_running_models", lambda: running)
    monkeypatch.setattr(om, "unload_model", fake_unload)

    result = om.ensure_only_model_loaded("qwen2.5:1.5b")
    assert result is True
    assert "qwen3:30b-a3b" in unloaded
    assert "qwen2.5:1.5b" not in unloaded


def test_can_fit_model_with_headroom(monkeypatch):
    monkeypatch.setattr(om, "available_memory_gb", lambda: 10.0)
    assert om.can_fit_model("qwen2.5:1.5b", headroom_gb=2.0) is True  # 0.75 + 2 = 2.75 < 10
    assert om.can_fit_model("qwen3:30b-a3b", headroom_gb=2.0) is False  # 15 + 2 = 17 > 10
