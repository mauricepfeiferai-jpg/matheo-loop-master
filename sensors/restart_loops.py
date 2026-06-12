"""S3: Crash-Loop-Erkennung ueber Restart-RATE (Delta), nicht absolute NRestarts
(empire=102124 loopte, synapse-bridge=12823 ist stabil). Plus OOM + Config-Smells.
Units in running,activating,failed scannen — Looper stehen oft in 'activating'."""
import json
import subprocess
import time
from pathlib import Path

from sensors.bus import Finding

STATE_PATH = Path("/var/lib/loop-master/restarts_state.json")


def detect_loops(prev: dict, curr: dict, min_rate_per_h: float = 10.0) -> list[Finding]:
    out: list[Finding] = []
    for unit, c in curr.items():
        p = prev.get(unit)
        if not p:
            continue
        dt_h = (c["ts"] - p["ts"]) / 3600.0
        if dt_h <= 0:
            continue
        rate = (c["nrestarts"] - p["nrestarts"]) / dt_h
        if rate >= min_rate_per_h:
            # Result=success = gewollter Dauerlauf (Restart-als-Timer, tailscale-watchdog-Fall)
            if c.get("result") == "success":
                out.append(Finding(sensor="restart_loops", severity="info",
                                   f_class="restart.timer-antipattern", subject=unit,
                                   evidence=f"{rate:.0f} Restarts/h mit Exit 0 — Restart=always als Timer missbraucht",
                                   suggested_fix=f"{unit} auf systemd-Timer umstellen (kosmetisch, kein Ausfall)"))
            else:
                out.append(Finding(sensor="restart_loops", severity="krit",
                                   f_class="restart.active-loop", subject=unit,
                                   evidence=f"{rate:.0f} Restarts/h (NRestarts {p['nrestarts']}->{c['nrestarts']}) — Restart heilt die Ursache nicht",
                                   suggested_fix=f"journalctl -u {unit} auf Exit-Ursache pruefen; NICHT weiter restarten"))
    return out


def _list_units() -> list[str]:
    r = subprocess.run(["systemctl", "list-units", "--type=service",
                        "--state=running,activating,failed", "--no-legend", "--no-pager", "--plain"],
                       capture_output=True, text=True, timeout=15)
    return [l.split()[0] for l in r.stdout.splitlines() if l.split() and l.split()[0].endswith(".service")]


def snapshot() -> dict:
    now = time.time()
    snap = {}
    for unit in _list_units():
        r = subprocess.run(["systemctl", "show", unit, "-p", "NRestarts", "-p", "Result"],
                           capture_output=True, text=True, timeout=10)
        vals = dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)
        try:
            snap[unit] = {"ts": now, "nrestarts": int(vals.get("NRestarts", "0") or 0),
                          "result": vals.get("Result", "unknown")}
        except ValueError:
            continue
    return snap


def check_oom() -> list[Finding]:
    out: list[Finding] = []
    # Journal-Retention hier nur ~10h (Looper-Churn) -> kern.log zusaetzlich
    r = subprocess.run("journalctl -k --since '24 hours ago' --no-pager 2>/dev/null | grep -ci 'out of memory\\|oom-kill' || true",
                       shell=True, capture_output=True, text=True, timeout=20)
    k = subprocess.run("grep -ci 'out of memory\\|oom-kill' /var/log/kern.log 2>/dev/null || true",
                       shell=True, capture_output=True, text=True, timeout=20)
    total = int(r.stdout.strip() or 0) + int(k.stdout.strip() or 0)
    if total > 0:
        out.append(Finding(sensor="restart_loops", severity="krit",
                           f_class="restart.oom-kill", subject="kernel",
                           evidence=f"{total} OOM-Events (journal 24h + kern.log)",
                           suggested_fix="Speicherfresser identifizieren; Looper NICHT blind wiederbeleben"))
    return out


def load_state(path: Path = STATE_PATH) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state))


def collect() -> list[Finding]:
    prev = load_state()
    curr = snapshot()
    findings = detect_loops(prev, curr)
    findings += check_oom()
    save_state(curr)
    return findings
