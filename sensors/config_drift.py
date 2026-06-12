"""S1: Konfig-Drift — die ollama-Klasse. Env-Konflikte ueber Drop-ins,
Pfad-Traversal fuer Dienst-User, verwaiste Drop-in-Dirs.
WICHTIG: systemctl show zeigt nur den Merge — Duplikate sieht nur `systemctl cat`."""
import os
import pwd
import re
import subprocess
from pathlib import Path

from sensors.bus import Finding

_SRC_RE = re.compile(r"^#\s+(/\S+)$")
_ENV_RE = re.compile(r'^Environment="?([A-Za-z0-9_]+)=([^"]*)"?')


def parse_unit_env(cat_output: str) -> dict[str, list[tuple[str, str]]]:
    """key -> Liste (wert, quelldatei) in Drop-in-Reihenfolge."""
    env: dict[str, list[tuple[str, str]]] = {}
    src = "?"
    for line in cat_output.splitlines():
        m = _SRC_RE.match(line.strip())
        if m:
            src = m.group(1)
            continue
        e = _ENV_RE.match(line.strip())
        if e:
            env.setdefault(e.group(1), []).append((e.group(2), src))
    return env


def find_env_conflicts(unit: str, env: dict[str, list[tuple[str, str]]]) -> list[Finding]:
    out: list[Finding] = []
    for key, defs in env.items():
        if len(defs) < 2:
            continue
        values = {v for v, _ in defs}
        srcs = ", ".join(s for _, s in defs)
        if len(values) > 1:
            winner = defs[-1][0]
            out.append(Finding(
                sensor="config_drift", severity="hoch",
                f_class="config-drift.env-conflict", subject=unit,
                evidence=f"{key} mehrfach mit UNTERSCHIEDLICHEN Werten ({srcs}); effektiv gewinnt '{winner}'",
                suggested_fix=f"Verlierer-Drop-in bereinigen; eine Wahrheit fuer {key}"))
        else:
            out.append(Finding(
                sensor="config_drift", severity="info",
                f_class="config-drift.env-duplicate", subject=unit,
                evidence=f"{key} redundant identisch definiert ({srcs})"))
    return out


def check_path_traversal(path: str, user: str) -> Finding | None:
    """Heuristik: kann `user` jede Parent-Ebene betreten? (Klassiker: /root=700)"""
    try:
        uinfo = pwd.getpwnam(user)
    except KeyError:
        return None
    p = Path(path)
    if not p.is_absolute():
        return None
    cur = Path("/")
    for part in p.parts[1:]:
        cur = cur / part
        try:
            st = os.stat(cur)
        except FileNotFoundError:
            return Finding(sensor="config_drift", severity="hoch",
                           f_class="config-drift.path-missing", subject=f"{user}:{path}",
                           evidence=f"Pfad-Element {cur} existiert nicht")
        except PermissionError:
            return None
        mode = st.st_mode
        if st.st_uid == uinfo.pw_uid:
            ok = bool(mode & 0o100)
        elif st.st_gid == uinfo.pw_gid:
            ok = bool(mode & 0o010)
        else:
            ok = bool(mode & 0o001)
        if cur.is_dir() and not ok:
            return Finding(sensor="config_drift", severity="krit",
                           f_class="config-drift.not-traversable", subject=f"{user}:{path}",
                           evidence=f"{cur} (mode {oct(mode & 0o777)}, owner uid {st.st_uid}) ist fuer User {user} nicht traversierbar — exakt die ollama-Klasse vom 2026-06-09",
                           suggested_fix=f"Daten von {path} aus dem gesperrten Baum verschieben (NICHT {cur} aufweichen)")
    return None


def find_orphaned_dropins() -> list[Finding]:
    out: list[Finding] = []
    base = Path("/etc/systemd/system")
    for d in sorted(base.glob("*.service.d")):
        unit = d.name.removesuffix(".d")
        r = subprocess.run(["systemctl", "show", unit, "-p", "LoadState", "--value"],
                           capture_output=True, text=True, timeout=10)
        if r.stdout.strip() == "not-found":
            out.append(Finding(sensor="config_drift", severity="info",
                               f_class="config-drift.orphan-dropin", subject=unit,
                               evidence=f"Drop-in-Dir {d} existiert, Unit ist not-found",
                               suggested_fix=f"{d} archivieren"))
    return out


def _nonroot_enabled_services() -> list[tuple[str, str]]:
    r = subprocess.run(["systemctl", "list-unit-files", "--state=enabled",
                        "--type=service", "--no-legend", "--no-pager"],
                       capture_output=True, text=True, timeout=15)
    out = []
    for line in r.stdout.splitlines():
        unit = line.split()[0] if line.split() else ""
        if not unit.endswith(".service"):
            continue
        u = subprocess.run(["systemctl", "show", unit, "-p", "User", "--value"],
                           capture_output=True, text=True, timeout=10)
        user = u.stdout.strip()
        if user and user != "root":
            out.append((unit, user))
    return out


def _unit_paths(unit: str) -> list[str]:
    r = subprocess.run(["systemctl", "show", unit, "-p", "Environment",
                        "-p", "WorkingDirectory", "--no-pager"],
                       capture_output=True, text=True, timeout=10)
    paths = re.findall(r"=(/[^\s:\"]+)", r.stdout)
    return [p for p in paths if "/" in p]


def collect() -> list[Finding]:
    findings: list[Finding] = []
    for unit, user in _nonroot_enabled_services():
        cat = subprocess.run(["systemctl", "cat", unit], capture_output=True, text=True, timeout=10)
        findings += find_env_conflicts(unit, parse_unit_env(cat.stdout))
        for p in _unit_paths(unit):
            f = check_path_traversal(p, user)
            if f:
                findings.append(f)
    findings += find_orphaned_dropins()
    return findings
