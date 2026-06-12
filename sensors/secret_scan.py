"""S5: Klartext-Secrets. Werte werden NIE geloggt/emittiert — nur Pfad,
Variablenname, Muster-Typ, Permissions. Bounded Scans (Runaway-Regel)."""
import os
import stat as statmod
from pathlib import Path

import re

from sensors.bus import Finding

PATTERNS = {
    "telegram": re.compile(r"\b\d{6,12}:AA[A-Za-z0-9_-]{30,}"),
    "github": re.compile(r"\b(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    "api-key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "aws": re.compile(r"\bAKIA[0-9A-Z]{16}"),
}
GIT_ROOT = Path("/root/repos")


def scan_file(path: Path) -> list[tuple[str, str]]:
    """Liefert (varname, pattern_name) — NIE den Wert."""
    hits: list[tuple[str, str]] = []
    try:
        text = path.read_text(errors="replace")
    except (PermissionError, IsADirectoryError, FileNotFoundError):
        return []
    for line in text.splitlines():
        for name, pat in PATTERNS.items():
            if pat.search(line):
                var = line.split("=", 1)[0].strip() if "=" in line else "<inline>"
                hits.append((var, name))
                break
    return hits


def _world_readable(path: Path) -> bool:
    return bool(os.stat(path).st_mode & statmod.S_IROTH)


def scan_env_files(root: Path) -> list[Finding]:
    out: list[Finding] = []
    for p in sorted(root.rglob(".env*")):
        if ".example" in p.name or not p.is_file():
            continue
        if len(p.relative_to(root).parts) > 4:   # bounded depth
            continue
        hits = scan_file(p)
        if hits:
            perms = oct(os.stat(p).st_mode & 0o777)
            wr = " WELTLESBAR" if _world_readable(p) else ""
            sev = "krit" if _world_readable(p) else "hoch"
            vars_ = ", ".join(f"{v}({t})" for v, t in hits)
            out.append(Finding(sensor="secret_scan", severity=sev,
                               f_class="secret.plaintext-env", subject=str(p),
                               evidence=f"Token-Muster: {vars_} (perms {perms}{wr})",
                               suggested_fix="Token rotieren + Datei nach Secret-Store/600 verschieben"))
    return out


def scan_git_configs(root: Path = GIT_ROOT) -> list[Finding]:
    out: list[Finding] = []
    if not root.exists():
        return out
    for cfg in sorted(root.glob("**/.git/config")):
        if len(cfg.relative_to(root).parts) > 6:   # bounded
            continue
        if scan_file(cfg):
            out.append(Finding(sensor="secret_scan", severity="krit",
                               f_class="secret.git-remote-token", subject=str(cfg),
                               evidence="Token-Muster in git remote URL",
                               suggested_fix="Remote auf SSH/credential-helper umstellen, Token rotieren"))
    return out


def collect() -> list[Finding]:
    findings: list[Finding] = []
    findings += scan_env_files(Path("/root/projects"))
    for p in sorted(Path("/etc/cron.d").iterdir()):
        if p.is_file() and scan_file(p):
            perms = oct(os.stat(p).st_mode & 0o777)
            findings.append(Finding(sensor="secret_scan", severity="hoch",
                                    f_class="secret.cron-env-token", subject=str(p),
                                    evidence=f"Token-Zuweisung in cron.d (perms {perms})",
                                    suggested_fix="Token in root-only EnvironmentFile auslagern + rotieren"))
    findings += scan_git_configs()
    return findings
