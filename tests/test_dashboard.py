import json

from sensors.dashboard import render


def _write_bus(path, findings):
    path.write_text("\n".join(json.dumps(f) for f in findings) + "\n")


def test_render_groups_by_severity(tmp_path):
    bus = tmp_path / "findings.jsonl"
    _write_bus(bus, [
        {"sensor": "s1", "severity": "krit", "f_class": "a.b", "subject": "x",
         "evidence": "e1", "suggested_fix": "f1", "ts": "2026-06-09T20:00:00+00:00"},
        {"sensor": "s2", "severity": "info", "f_class": "c.d", "subject": "y",
         "evidence": "e2", "suggested_fix": "", "ts": "2026-06-09T20:01:00+00:00"},
    ])
    out = render(bus_path=bus)
    assert "KRIT (1)" in out
    assert "INFO (1)" in out
    assert "a.b" in out and "e1" in out


def test_render_dedupes_repeated_findings(tmp_path):
    bus = tmp_path / "findings.jsonl"
    same = {"sensor": "s1", "severity": "hoch", "f_class": "a.b", "subject": "x",
            "evidence": "e1", "suggested_fix": "", "ts": "2026-06-09T20:00:00+00:00"}
    _write_bus(bus, [same, dict(same, ts="2026-06-09T21:00:00+00:00")])
    out = render(bus_path=bus)
    assert "HOCH (1)" in out          # dedupliziert auf f_class+subject
    assert "2x" in out                # aber Anzahl sichtbar


def test_render_empty_bus(tmp_path):
    bus = tmp_path / "findings.jsonl"
    bus.write_text("")
    out = render(bus_path=bus)
    assert "Keine Findings" in out
