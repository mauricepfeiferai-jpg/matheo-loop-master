import json
from pathlib import Path
from unittest.mock import patch

from hecate.model_benchmark import benchmark_all, pick_fastest_per_task


def test_benchmark_runs_and_returns_results(tmp_path, monkeypatch):
    monkeypatch.setattr("hecate.model_benchmark.OLLAMA_HOST", "http://127.0.0.1:11434")
    # Kurzes Timeout, damit Test nicht hängt
    monkeypatch.setattr("hecate.model_benchmark.MODELS", {})

    results = benchmark_all()
    assert isinstance(results, dict)


def test_pick_fastest_per_task_selects_minimum_elapsed():
    results = {
        "classify": [
            {"model": "a", "ok": True, "elapsed": 1.0},
            {"model": "b", "ok": True, "elapsed": 0.5},
        ],
        "reason": [
            {"model": "c", "ok": False, "elapsed": 5.0},
        ],
    }
    picks = pick_fastest_per_task(results)
    assert picks["classify"]["model"] == "b"
    assert picks["reason"] is None
