#!/usr/bin/env python3
"""Docker Health Sensor — Container-Status prüfen.

Schließt Lücke #15: Fehlende Sensoren.
"""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BUS = Path("/var/lib/loop-master/findings.jsonl")

def collect():
    try:
        r = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}|{{.Status}}|{{.Image}}"],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            emit("docker_not_available", "info", "Docker nicht erreichbar oder nicht installiert")
            return

        lines = [l for l in r.stdout.strip().split("\n") if l.strip()]
        if not lines:
            emit("no_containers", "info", "Keine Docker-Container laufen")
            return

        for line in lines:
            parts = line.split("|")
            if len(parts) >= 2:
                name, status = parts[0], parts[1]
                if "unhealthy" in status.lower():
                    emit(f"docker_unhealthy_{name}", "hoch", f"Container {name} unhealthy: {status}")
                elif "restarting" in status.lower():
                    emit(f"docker_restarting_{name}", "mittel", f"Container {name} restarting: {status}")
                elif "exited" in status.lower():
                    emit(f"docker_exited_{name}", "hoch", f"Container {name} exited: {status}")

    except subprocess.TimeoutExpired:
        emit("docker_timeout", "mittel", "docker ps Timeout nach 15s")
    except FileNotFoundError:
        emit("docker_missing", "info", "Docker nicht installiert")
    except Exception as e:
        emit("docker_error", "info", str(e)[:200])

def emit(f_class: str, severity: str, evidence: str):
    finding = {
        "sensor": "docker_health",
        "severity": severity,
        "f_class": f"docker.{f_class}",
        "subject": f"Docker: {f_class}",
        "evidence": evidence,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with open(BUS, "a") as f:
        f.write(json.dumps(finding, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    collect()
