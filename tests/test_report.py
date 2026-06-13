import json

from hecate.report import build_report, new_since_last, send_via_hermes


def test_send_via_hermes_uses_stdin_pipe():
    seen = {}

    def fake_runner(cmd, inp):
        seen["cmd"], seen["inp"] = cmd, inp
        return 0

    assert send_via_hermes("hallo report", runner=fake_runner) is True
    assert seen["cmd"][:3] == ["hermes", "send", "--to"]
    assert "telegram" in seen["cmd"]
    assert seen["inp"] == "hallo report"


def test_send_via_hermes_false_on_failure():
    assert send_via_hermes("x", runner=lambda c, i: 1) is False


def _events(tmp_path, events):
    bus = tmp_path / "findings.jsonl"
    bus.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return bus


def test_report_contains_only_krit_and_hoch(tmp_path):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    bus = _events(tmp_path, [
        {"sensor": "s", "severity": "krit", "f_class": "a", "subject": "x", "evidence": "e", "suggested_fix": "", "ts": now},
        {"sensor": "s", "severity": "info", "f_class": "b", "subject": "y", "evidence": "e", "suggested_fix": "", "ts": now},
    ])
    rep = build_report(bus_path=bus)
    assert "a @ x" in rep
    assert "b @ y" not in rep


def test_report_drops_stale_events(tmp_path):
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    bus = _events(tmp_path, [
        {"sensor": "s", "severity": "krit", "f_class": "alt", "subject": "behoben", "evidence": "e", "suggested_fix": "", "ts": (now - timedelta(hours=24)).isoformat()},
        {"sensor": "s", "severity": "krit", "f_class": "neu", "subject": "offen", "evidence": "e", "suggested_fix": "", "ts": now.isoformat()},
    ])
    rep = build_report(bus_path=bus)
    assert "neu @ offen" in rep
    assert "behoben" not in rep


def test_new_since_last_dedupes_against_state(tmp_path):
    bus = _events(tmp_path, [
        {"sensor": "s", "severity": "krit", "f_class": "a", "subject": "x", "evidence": "e", "suggested_fix": "", "ts": "2026-06-10T01:00:00+00:00"},
    ])
    state = tmp_path / "reported.json"
    first = new_since_last(bus_path=bus, state_path=state)
    assert len(first) == 1
    second = new_since_last(bus_path=bus, state_path=state)
    assert second == []  # schon gemeldet -> nie doppelt spammen
