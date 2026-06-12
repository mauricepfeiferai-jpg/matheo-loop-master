#!/usr/bin/env python3
"""Network Latency Sensor — Ping zu kritischen Endpoints.

Schließt Lücke #15: Fehlende Sensoren.
"""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BUS = Path("/var/lib/loop-master/findings.jsonl")
TARGETS = [
    ("8.8.8.8", "Google DNS"),
    ("1.1.1.1", "Cloudflare DNS"),
    ("hetzner.com", "Hetzner"),
]

def collect():
    for host, label in TARGETS:
        try:
            r = subprocess.run(
                ["ping", "-c", "3", "-W", "2", host],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode != 0:
                emit(f"ping_fail_{label}", "hoch", f"Ping zu {label} ({host}) fehlgeschlagen")
                continue

            # Parse avg time
            lines = r.stdout.split("\n")
            avg_ms = None
            for line in lines:
                if "avg" in line and "/" in line:
                    try:
                        parts = line.split("/")
                        if len(parts) >= 5:
                            avg_ms = float(parts[4])
                    except (ValueError, IndexError):
                        pass

            if avg_ms and avg_ms > 200:
                emit(f"ping_slow_{label}", "mittel", f"Ping zu {label} langsam: {avg_ms:.1f}ms")
            elif avg_ms:
                emit(f"ping_ok_{label}", "info", f"Ping zu {label}: {avg_ms:.1f}ms")

        except subprocess.TimeoutExpired:
            emit(f"ping_timeout_{label}", "hoch", f"Ping zu {label} Timeout")
        except FileNotFoundError:
            emit("ping_missing", "info", "ping nicht verfügbar")
        except Exception as e:
            emit(f"ping_error_{label}", "info", str(e)[:200])

def emit(f_class: str, severity: str, evidence: str):
    finding = {
        "sensor": "network_latency",
        "severity": severity,
        "f_class": f"net.{f_class}",
        "subject": f"Netz: {f_class}",
        "evidence": evidence,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with open(BUS, "a") as f:
        f.write(json.dumps(finding, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    collect()
