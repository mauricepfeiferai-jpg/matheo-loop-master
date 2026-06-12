"""Findings-Bus: append-only JSONL mit flock (Lektion: synapse_bus touch-Lock-Race)."""
import fcntl
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

BUS_PATH = Path("/var/lib/loop-master/findings.jsonl")


@dataclass
class Finding:
    sensor: str
    severity: str          # krit | hoch | info
    f_class: str           # z.B. "config-drift.env-conflict"
    subject: str           # Unit / Pfad / Endpunkt
    evidence: str          # menschenlesbar, NIE Secrets
    suggested_fix: str = ""
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def rotate_if_big(bus_path: Path = BUS_PATH, max_bytes: int = 10 * 1024 * 1024) -> None:
    """Eine Generation Rotation (nerve-pulse-Lektion: nie unbegrenzt wachsen)."""
    if bus_path.exists() and bus_path.stat().st_size > max_bytes:
        bus_path.replace(bus_path.with_suffix(bus_path.suffix + ".1"))


def emit(findings: list[Finding], bus_path: Path = BUS_PATH) -> None:
    bus_path.parent.mkdir(parents=True, exist_ok=True)
    with open(bus_path, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            for fd in findings:
                f.write(json.dumps(asdict(fd), ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
