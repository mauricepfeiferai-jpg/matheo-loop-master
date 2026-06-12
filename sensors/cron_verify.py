"""S4: still-failende Crons. Faengt die 4 belegten Fehlerklassen:
fehlendes User-Feld (ganze cron.d-Datei ignoriert!), fehlendes Ziel-Skript
(auch hinter Interpreter), fehlendes Redirect-Verzeichnis, tote Eintraege.
[PAUSED]-Marker werden respektiert (Kommentar = skip)."""
import pwd
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from sensors.bus import Finding

_INTERP = {"python3", "python", "bash", "sh", "/usr/bin/python3", "/bin/bash", "/bin/sh"}


@dataclass
class CronEntry:
    source: str
    user: str | None
    command: str
    raw: str


def parse_cron_text(text: str, source: str, needs_user: bool) -> list[CronEntry]:
    entries: list[CronEntry] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" in line.split()[0]:
            continue
        parts = line.split()
        if len(parts) < (7 if needs_user else 6):
            continue
        if needs_user:
            user = parts[5]
            cmd = " ".join(parts[6:])
        else:
            user = None
            cmd = " ".join(parts[5:])
        entries.append(CronEntry(source=source, user=user, command=cmd, raw=raw))
    return entries


def _extract_script(cmd: str) -> str | None:
    toks = cmd.split()
    if not toks:
        return None
    if Path(toks[0]).name in {Path(i).name for i in _INTERP} and len(toks) > 1:
        for t in toks[1:]:
            if not t.startswith("-"):
                return t
    return toks[0]


def _redirect_target(cmd: str) -> str | None:
    m = re.search(r">>?\s*(\S+)", cmd)
    return m.group(1) if m else None


def check_entries(entries: list[CronEntry]) -> list[Finding]:
    out: list[Finding] = []
    for e in entries:
        if e.user is not None:
            try:
                pwd.getpwnam(e.user)
            except KeyError:
                out.append(Finding(sensor="cron_verify", severity="krit",
                                   f_class="cron.bad-user-field", subject=e.source,
                                   evidence=f"User-Feld '{e.user}' ungueltig — cron ignoriert die GANZE Datei (Fall gpe-legal-intelligence)",
                                   suggested_fix=f"6. Feld in {e.source} muss gueltiger User sein (z.B. root)"))
                continue
        script = _extract_script(e.command)
        if script and script.startswith("/") and not Path(script).exists():
            out.append(Finding(sensor="cron_verify", severity="hoch",
                               f_class="cron.target-missing", subject=e.source,
                               evidence=f"Ziel {script} existiert nicht",
                               suggested_fix="Eintrag fixen oder archivieren"))
        rd = _redirect_target(e.command)
        if rd and rd.startswith("/") and not Path(rd).parent.exists():
            out.append(Finding(sensor="cron_verify", severity="hoch",
                               f_class="cron.redirect-dir-missing", subject=e.source,
                               evidence=f"Log-Verzeichnis {Path(rd).parent} fehlt — Job laeuft nie (Fall gpe-revenue-tracker)",
                               suggested_fix=f"mkdir -p {Path(rd).parent} oder Eintrag fixen"))
    return out


def collect() -> list[Finding]:
    entries: list[CronEntry] = []
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
    if r.returncode == 0:
        entries += parse_cron_text(r.stdout, source="root-crontab", needs_user=False)
    for f in sorted(Path("/etc/cron.d").iterdir()):
        if f.is_file() and not f.name.endswith((".disabled", ".bak")):
            try:
                entries += parse_cron_text(f.read_text(), source=str(f), needs_user=True)
            except (PermissionError, UnicodeDecodeError):
                continue
    return check_entries(entries)
