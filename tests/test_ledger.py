from hecate.ledger import Ledger


def _led(tmp_path):
    return Ledger(db_path=str(tmp_path / "ledger.db"))


def test_finish_with_real_output_is_ok(tmp_path):
    led = _led(tmp_path)
    art = tmp_path / "export.md"
    art.write_text("x" * 500)
    rid = led.start("test-loop", phase="EXPORT")
    assert led.finish(rid, output_path=str(art)) == "ok"


def test_small_output_is_empty_output_never_ok(tmp_path):
    # Der 67B-Fall: Stub-Output darf NIE als ok gelten
    led = _led(tmp_path)
    art = tmp_path / "stub.md"
    art.write_text("x" * 67)
    rid = led.start("test-loop")
    assert led.finish(rid, output_path=str(art)) == "empty_output"


def test_no_proof_is_failed(tmp_path):
    # Kein output_path + kein Status = kein Beweis = failed
    led = _led(tmp_path)
    rid = led.start("test-loop")
    assert led.finish(rid) == "failed"


def test_missing_output_file_is_failed(tmp_path):
    led = _led(tmp_path)
    rid = led.start("test-loop")
    assert led.finish(rid, output_path=str(tmp_path / "gibtsnicht.md")) == "failed"


def test_double_finish_rejected(tmp_path):
    led = _led(tmp_path)
    rid = led.start("test-loop")
    led.finish(rid, status="skipped")
    try:
        led.finish(rid, status="skipped")
        assert False, "doppeltes finish muss abgelehnt werden"
    except SystemExit:
        pass


def test_stale_finds_loop_without_ok(tmp_path):
    led = _led(tmp_path)
    rid = led.start("nie-ok-loop")
    led.finish(rid, status="failed")
    stale = led.stale(hours=1)
    assert any(name == "nie-ok-loop" for name, _ in stale)
