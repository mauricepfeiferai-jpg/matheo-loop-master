import json
from pathlib import Path

from hecate.context_compactor import (
    CompactionConfig,
    compact_findings,
    compact_proposals,
    compact_text,
    summarize_findings,
)


def test_compact_findings_deduplicates_by_class_subject():
    findings = [
        {"severity": "krit", "sensor": "disk", "f_class": "disk.full", "subject": "/", "evidence": "95%", "ts": "2026-06-13T10:00:00+00:00"},
        {"severity": "krit", "sensor": "disk", "f_class": "disk.full", "subject": "/", "evidence": "96%", "ts": "2026-06-13T10:05:00+00:00"},
    ]
    result = compact_findings(findings)
    assert len(result) == 1
    assert result[0]["evidence"] == "96%"


def test_compact_findings_filters_old_entries(tmp_path):
    old = "2026-06-10T10:00:00+00:00"
    new = "2026-06-13T10:00:00+00:00"
    findings = [
        {"severity": "krit", "sensor": "x", "f_class": "y", "subject": "z", "evidence": "old", "ts": old},
        {"severity": "krit", "sensor": "x", "f_class": "y2", "subject": "z2", "evidence": "new", "ts": new},
    ]
    result = compact_findings(findings, CompactionConfig(max_age_hours=24))
    assert len(result) == 1
    assert result[0]["evidence"] == "new"


def test_compact_findings_sorts_by_severity():
    findings = [
        {"severity": "mittel", "sensor": "a", "f_class": "b", "subject": "c", "evidence": "i", "ts": "2026-06-13T10:00:00+00:00"},
        {"severity": "krit", "sensor": "a", "f_class": "b", "subject": "c2", "evidence": "k", "ts": "2026-06-13T10:00:00+00:00"},
        {"severity": "hoch", "sensor": "a", "f_class": "b", "subject": "c3", "evidence": "h", "ts": "2026-06-13T10:00:00+00:00"},
    ]
    result = compact_findings(findings)
    assert result[0]["severity"] == "krit"
    assert result[1]["severity"] == "hoch"
    assert result[2]["severity"] == "mittel"


def test_compact_findings_limits_items():
    findings = [
        {"severity": "hoch", "sensor": "s", "f_class": f"f{i}", "subject": "sub", "evidence": "x", "ts": "2026-06-13T10:00:00+00:00"}
        for i in range(50)
    ]
    result = compact_findings(findings, CompactionConfig(max_items=5))
    assert len(result) == 5


def test_compact_text_shortens_long_text():
    long = "\n".join(f"line {i}" for i in range(200))
    result = compact_text(long, max_lines=20)
    assert len(result.splitlines()) <= 25  # inklusive "..."


def test_summarize_findings_returns_markdown():
    findings = [
        {"severity": "krit", "sensor": "disk", "f_class": "disk.full", "subject": "/", "evidence": "95%", "ts": "2026-06-13T10:00:00+00:00"},
    ]
    md = summarize_findings(findings)
    assert "1 relevante Findings" in md
    assert "🔴" in md
    assert "disk.full" in md


def test_compact_proposals_reads_titles(tmp_path):
    p1 = tmp_path / "prop1.md"
    p1.write_text("# Fix disk\n\nBody text")
    p2 = tmp_path / "prop2.md"
    p2.write_text("# Add sensor\n\nMore body")

    result = compact_proposals([p1, p2])
    assert len(result) == 2
    titles = {r["title"] for r in result}
    assert "Fix disk" in titles
    assert "Add sensor" in titles
