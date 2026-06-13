from pathlib import Path
from unittest.mock import MagicMock, patch

from hecate import subagent_research as sr


def test_sidechain_path_unique():
    p1 = sr._sidechain_path("question A")
    p2 = sr._sidechain_path("question B")
    assert p1 != p2
    assert p1.parent.name == "sidechains"


def test_run_research_writes_sidechain_and_returns_summary(tmp_path, monkeypatch):
    sidechain_dir = tmp_path / "sidechains"
    monkeypatch.setattr(sr, "SIDECHAIN_DIR", sidechain_dir)

    fake_gate = MagicMock()
    fake_gate.run.return_value = {
        "success": True,
        "response": "Kernbefund: lokale Modelle sind langsam. Empfehlung: GPU.",
        "decision": {"model": "qwen2.5:1.5b", "provider": "ollama"},
        "latency_ms": 5000,
    }
    monkeypatch.setattr(sr, "ModelRouteGate", lambda: fake_gate)

    result = sr.run_research("Wie beschleunige ich lokale Modelle?")
    assert result["success"] is True
    assert "GPU" in result["summary"]
    assert result["sidechain_path"] is not None
    assert Path(result["sidechain_path"]).exists()


def test_enrich_research_brief_inserts_section(tmp_path, monkeypatch):
    sidechain_dir = tmp_path / "sidechains"
    monkeypatch.setattr(sr, "SIDECHAIN_DIR", sidechain_dir)

    fake_gate = MagicMock()
    fake_gate.run.return_value = {
        "success": True,
        "response": "Zusammenfassung der Forschung.",
        "decision": {"model": "qwen2.5:1.5b", "provider": "ollama"},
        "latency_ms": 3000,
    }
    monkeypatch.setattr(sr, "ModelRouteGate", lambda: fake_gate)

    brief = [
        "# Brief",
        "",
        "## Leitplanken",
        "Reversibel.",
    ]
    enriched = sr.enrich_research_brief_with_sidechains(brief, question="Testfrage")
    assert any("Subagent-Research" in line for line in enriched)
    assert any("Testfrage" in line for line in enriched)


def test_run_research_failure_returns_error(monkeypatch):
    fake_gate = MagicMock()
    fake_gate.run.return_value = {
        "success": False,
        "error": "timeout",
    }
    monkeypatch.setattr(sr, "ModelRouteGate", lambda: fake_gate)

    result = sr.run_research("Frage")
    assert result["success"] is False
    assert result["error"] == "timeout"
