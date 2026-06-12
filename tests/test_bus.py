import json

from sensors.bus import Finding, emit


def test_emit_appends_valid_jsonl(tmp_path):
    bus = tmp_path / "findings.jsonl"
    f1 = Finding(sensor="test", severity="info", f_class="t.a", subject="x", evidence="e1")
    f2 = Finding(sensor="test", severity="krit", f_class="t.b", subject="y", evidence="e2", suggested_fix="fix it")
    emit([f1], bus_path=bus)
    emit([f2], bus_path=bus)
    lines = bus.read_text().strip().splitlines()
    assert len(lines) == 2
    rec = json.loads(lines[1])
    assert rec["severity"] == "krit"
    assert rec["suggested_fix"] == "fix it"
    assert rec["ts"]  # timestamp gesetzt


def test_emit_creates_parent_dir(tmp_path):
    bus = tmp_path / "deep" / "findings.jsonl"
    emit([Finding(sensor="t", severity="info", f_class="c", subject="s", evidence="e")], bus_path=bus)
    assert bus.exists()
