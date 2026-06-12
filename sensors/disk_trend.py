"""S2: Disk-Prognose. Eigene Zeitreihe (keine existiert am System; sysstat sammelt kein FS).
Lineare Regression ueber die letzten Samples -> Stunden-bis-voll."""
import json
import os
import time
from pathlib import Path

from sensors.bus import Finding

SERIES_PATH = Path("/var/lib/loop-master/disk_trend.jsonl")
WARN_HOURS = 48.0
WARN_PCT = 92.0
MAX_SAMPLES = 288  # ~3 Tage bei 15-min-Takt


def take_sample(mount: str = "/") -> dict:
    st = os.statvfs(mount)
    size = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    return {"ts": time.time(), "used": size - free, "size": size}


def load_series(path: Path = SERIES_PATH) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def append_sample(sample: dict, path: Path = SERIES_PATH) -> list[dict]:
    series = load_series(path)[-(MAX_SAMPLES - 1):] + [sample]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(s) for s in series) + "\n")
    return series


def hours_to_full(samples: list[dict]) -> float | None:
    """Least-Squares-Steigung used(t); None wenn <3 Samples oder nicht wachsend."""
    if len(samples) < 3:
        return None
    n = len(samples)
    t0 = samples[0]["ts"]
    xs = [(s["ts"] - t0) for s in samples]
    ys = [s["used"] for s in samples]
    mx, my = sum(xs) / n, sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom  # bytes/s
    if slope <= 0:
        return None
    free = samples[-1]["size"] - samples[-1]["used"]
    return (free / slope) / 3600.0


def collect() -> list[Finding]:
    sample = take_sample("/")
    series = append_sample(sample)
    findings: list[Finding] = []
    pct = sample["used"] / sample["size"] * 100
    if pct >= WARN_PCT:
        findings.append(Finding(sensor="disk_trend", severity="hoch",
                                f_class="disk.high-watermark", subject="/",
                                evidence=f"/ bei {pct:.1f}% (Schwelle {WARN_PCT}%)",
                                suggested_fix="Top-Verbraucher pruefen: ollama-Models 128G, /backup 30G, docker 19G"))
    h = hours_to_full(series)
    if h is not None and h < WARN_HOURS:
        sev = "krit" if h < 12 else "hoch"
        findings.append(Finding(sensor="disk_trend", severity=sev,
                                f_class="disk.trend-to-full", subject="/",
                                evidence=f"Prognose: / in ~{h:.1f}h voll (linear, {len(series)} Samples)",
                                suggested_fix="Wachstumsquelle identifizieren BEVOR die Klippe kommt (15.05. wiederholt sich sonst)"))
    return findings
