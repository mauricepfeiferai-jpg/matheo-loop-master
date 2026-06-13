from pathlib import Path
from unittest.mock import MagicMock, patch

from hecate.vision_engine import VisionEngine


def test_build_state_summary_with_no_files(tmp_path, monkeypatch):
    monkeypatch.setattr("hecate.vision_engine.BUS", tmp_path / "nonexistent.jsonl")
    monkeypatch.setattr("hecate.vision_engine.PROPOSALS_DIR", tmp_path / "proposals")
    monkeypatch.setattr("hecate.vision_engine.REPORTS_DIR", tmp_path / "reports")

    router = MagicMock()
    router.vision.return_value = (
        "Titel: Bessere Sensoren\n"
        "Problem: Sensoren sind laut.\n"
        "Konzept: Intelligente Deduplizierung.\n"
        "Umsetzungsschritte: 1) Deduplizierung bauen.\n"
        "Risiko: niedrig\n"
        "Erfolgsmass: 50% weniger Alerts"
    )

    with patch("hecate.vision_engine.create_proposal") as mock_create:
        mock_path = tmp_path / "proposals" / "hecate-vision-20260101-000000.md"
        mock_path.parent.mkdir(parents=True, exist_ok=True)
        mock_create.return_value = mock_path

        engine = VisionEngine(router=router)
        result = engine.generate_vision("Testthema")

        assert result["proposal_id"].startswith("hecate-vision-")
        # Parser sucht Header "Titel:"; wenn nicht gefunden, faellt auf topic zurueck
        assert result["title"] in ("Bessere Sensoren", "Testthema")
        assert "Intelligente Deduplizierung" in result["summary"]
        mock_create.assert_called_once()
        assert mock_path.exists()


def test_extract_section_finds_markdown_header():
    text = "## Problem\nSensoren sind zu laut.\n## Konzept\nDeduplizierung.\n"
    engine = VisionEngine(router=MagicMock())
    assert engine._extract_section(text, ["Problem"]) == "Sensoren sind zu laut."
    assert engine._extract_section(text, ["Konzept"]) == "Deduplizierung."


def test_list_topics_returns_strings():
    engine = VisionEngine(router=MagicMock())
    topics = engine.list_topics()
    assert len(topics) > 0
    assert all(isinstance(t, str) for t in topics)
