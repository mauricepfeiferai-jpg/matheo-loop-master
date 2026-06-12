from sensors.bus import Finding, emit, rotate_if_big


def test_rotates_when_over_limit(tmp_path):
    bus = tmp_path / "findings.jsonl"
    bus.write_text("x" * 100)
    rotate_if_big(bus, max_bytes=50)
    assert not bus.exists()
    assert (tmp_path / "findings.jsonl.1").read_text() == "x" * 100


def test_no_rotation_under_limit(tmp_path):
    bus = tmp_path / "findings.jsonl"
    bus.write_text("klein")
    rotate_if_big(bus, max_bytes=10_000)
    assert bus.read_text() == "klein"
    assert not (tmp_path / "findings.jsonl.1").exists()


def test_rotation_keeps_only_one_generation(tmp_path):
    bus = tmp_path / "findings.jsonl"
    (tmp_path / "findings.jsonl.1").write_text("alt")
    bus.write_text("y" * 100)
    rotate_if_big(bus, max_bytes=50)
    assert (tmp_path / "findings.jsonl.1").read_text() == "y" * 100  # alt ueberschrieben
