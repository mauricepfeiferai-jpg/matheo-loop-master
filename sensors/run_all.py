"""Runner: fuehrt alle Sensoren aus, isoliert Fehler. Ein crashender Sensor
wird selbst zum Finding statt den Lauf zu killen (health-sentinel-Lektion:
225/225 Laeufe starben an EINEM Check)."""
import sys
from pathlib import Path

from sensors.bus import BUS_PATH, Finding, emit, rotate_if_big


def run_sensors(sensors: dict, bus_path: Path = BUS_PATH) -> dict:
    rotate_if_big(bus_path)
    summary: dict = {}
    for name, collect in sensors.items():
        try:
            findings = collect()
            emit(findings, bus_path=bus_path)
            summary[name] = len(findings)
        except Exception as exc:  # noqa: BLE001 — bewusst breit: Isolation ist der Zweck
            emit([Finding(sensor=name, severity="hoch", f_class="sensor-error",
                          subject=name, evidence=f"Sensor crashte: {type(exc).__name__}: {exc}")],
                 bus_path=bus_path)
            summary[name] = "ERROR"
    return summary


def main() -> int:
    from sensors import (cert_expiry, config_drift, cron_verify, disk_trend,
                         ledger_stale, restart_loops, secret_scan)
    sensors = {
        "config_drift": config_drift.collect,
        "disk_trend": disk_trend.collect,
        "restart_loops": restart_loops.collect,
        "cron_verify": cron_verify.collect,
        "secret_scan": secret_scan.collect,
        "cert_expiry": cert_expiry.collect,
        "ledger_stale": ledger_stale.collect,
    }
    summary = run_sensors(sensors)
    for name, count in summary.items():
        print(f"{name}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
