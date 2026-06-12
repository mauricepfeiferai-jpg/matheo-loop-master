from hecate.ledger import Ledger
from sensors.ledger_stale import collect_from


def test_stale_loop_becomes_finding(tmp_path):
    led = Ledger(db_path=str(tmp_path / "l.db"))
    rid = led.start("toter-loop")
    led.finish(rid, status="failed")
    fnds = collect_from(led, hours=1)
    assert len(fnds) == 1
    assert fnds[0].f_class == "ledger.stale-loop"
    assert "toter-loop" in fnds[0].subject


def test_healthy_loop_is_silent(tmp_path):
    led = Ledger(db_path=str(tmp_path / "l.db"))
    art = tmp_path / "out.md"
    art.write_text("x" * 500)
    rid = led.start("gesunder-loop")
    led.finish(rid, output_path=str(art))
    assert collect_from(led, hours=1) == []


def test_empty_ledger_is_silent(tmp_path):
    led = Ledger(db_path=str(tmp_path / "l.db"))
    assert collect_from(led, hours=1) == []
