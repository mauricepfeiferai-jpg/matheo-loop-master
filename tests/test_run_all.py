from sensors.bus import Finding
from sensors.run_all import run_sensors


def test_crashing_sensor_does_not_kill_run(tmp_path):
    bus = tmp_path / "findings.jsonl"

    def good():
        return [Finding(sensor="good", severity="info", f_class="g", subject="s", evidence="ok")]

    def bad():
        raise RuntimeError("kaputt")

    summary = run_sensors({"good": good, "bad": bad}, bus_path=bus)
    assert summary["good"] == 1
    assert summary["bad"] == "ERROR"
    text = bus.read_text()
    assert "sensor-error" in text     # Crash wurde selbst zum Finding
    assert "ok" in text               # guter Sensor lief trotzdem
