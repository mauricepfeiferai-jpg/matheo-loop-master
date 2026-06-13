#!/usr/bin/env python3
"""HECATE Total Legacy Discovery — read-only Inventarisierung des Hetzner-Servers.

Scannt definierte Bereiche, erzeugt ein Inventar-JSON und daraus Decision Cards.
Keine Mutationen. Kein Lesen von Secrets/Legal/Kunden/Trading-Inhalten.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hecate.ledger import Ledger

DISCOVERY_DIR = Path("/var/lib/loop-master/discovery")
INVENTORY_PATH = DISCOVERY_DIR / "hetzner_inventory.json"
DECISION_DIR = Path("/root/projects/loop-master/decision_cards")
TRUST_BOUNDARY_SKIP = {
    "/root/.hermes",
    "/root/.ssh",
    "/root/.gnupg",
    "/root/.aws",
    "/root/.docker",
    "/root/vault/brain",
    "/root/vault/legal",
    "/root/vault/maurice",
    "/root/projects/legal",
    "/root/projects/gpe-core/empire-live-trader",
    "/root/projects/content-engine/crm",
}
SENSITIVE_NAME_RE = re.compile(
    r"\b(secret|token|key|password|pass|credential|env|\.env|private|legal|law|client|kunde|customer|patient|bank|trading-live|live-trade)\b",
    re.IGNORECASE,
)


@dataclass
class DiscoveredItem:
    id: str
    system: str = "hetzner"
    path: str = ""
    item_type: str = "unknown"
    size_bytes: int = 0
    last_modified_days: float = 0.0
    git_status: str = "unknown"
    languages: list[str] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)
    has_readme: bool = False
    has_tests: bool = False
    has_docker: bool = False
    systemd_refs: list[str] = field(default_factory=list)
    cron_refs: list[str] = field(default_factory=list)
    related_ports: list[int] = field(default_factory=list)
    secret_risk: bool = False
    legal_privacy_risk: bool = False
    business_value: int = 0
    system_value: int = 0
    risk_score: int = 0
    integration_potential: int = 0
    deletability: int = 0
    impact_100x: int = 0
    decision_class: str = "NEEDS_HUMAN_CONTEXT"
    evidence: list[str] = field(default_factory=list)
    recommended_action: str = ""
    next_safe_step: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dir_size(p: Path) -> int:
    total = 0
    try:
        for entry in os.scandir(p):
            if entry.is_dir(follow_symlinks=False):
                total += _dir_size(Path(entry.path))
            else:
                total += entry.stat(follow_symlinks=False).st_size
    except (PermissionError, OSError):
        pass
    return total


def _age_days(p: Path) -> float:
    try:
        return (time.time() - p.stat().st_mtime) / 86400.0
    except Exception:
        return 0.0


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception as exc:
        return -1, "", str(exc)


def _is_in_trust_boundary(p: Path) -> bool:
    """True wenn Pfad gelesen werden darf."""
    sp = str(p)
    for skip in TRUST_BOUNDARY_SKIP:
        if sp.startswith(skip):
            return False
    return True


def _git_status(path: Path) -> str:
    git_dir = path / ".git"
    if not git_dir.exists():
        return "no_git"
    rc, out, _ = _run(["git", "-C", str(path), "status", "--short"], timeout=10)
    if rc != 0:
        return "git_error"
    if not out.strip():
        return "clean"
    return "dirty"


def _detect_languages(path: Path) -> list[str]:
    exts: dict[str, int] = {}
    try:
        for root, _, files in os.walk(path):
            for f in files:
                ext = Path(f).suffix.lstrip(".").lower()
                if ext in ("py", "js", "ts", "sh", "yml", "yaml", "json", "md", "html", "css", "go", "rs", "swift"):
                    exts[ext] = exts.get(ext, 0) + 1
    except Exception:
        pass
    return sorted(exts, key=exts.get, reverse=True)[:5]


def _find_entrypoints(path: Path) -> list[str]:
    candidates = [
        "main.py", "server.py", "app.py", "run.py", "start.sh", "run.sh",
        "setup.py", "pyproject.toml", "requirements.txt", "package.json", "docker-compose.yml",
        "README.md", "AGENTS.md", "CLAUDE.md",
    ]
    found = []
    for c in candidates:
        if (path / c).exists():
            found.append(c)
    return found


def _has_docker_refs(path: Path) -> bool:
    return any((path / n).exists() for n in ["Dockerfile", "docker-compose.yml", ".dockerignore"])


def _has_tests(path: Path) -> bool:
    for name in ["tests", "test", "spec", "__tests__"]:
        if (path / name).is_dir():
            return True
    return False


def _related_systemd_services(name: str) -> list[str]:
    rc, out, _ = _run(["systemctl", "list-units", "--type=service", "--state=running", "--no-pager", "--plain"], timeout=15)
    if rc != 0:
        return []
    services = []
    for line in out.splitlines():
        line = line.strip()
        if not line or ".service" not in line:
            continue
        svc = line.split()[0]
        if name.lower() in svc.lower():
            services.append(svc)
    return services[:5]


def _related_crons(name: str) -> list[str]:
    refs = []
    for cron_dir in ["/etc/cron.d", "/etc/crontab", "/var/spool/cron/crontabs"]:
        p = Path(cron_dir)
        if not p.exists():
            continue
        try:
            for f in p.iterdir() if p.is_dir() else [p]:
                if f.is_file() and name.lower() in f.read_text(errors="replace").lower():
                    refs.append(str(f))
        except Exception:
            pass
    return refs[:5]


def _classify_and_score(item: DiscoveredItem) -> DiscoveredItem:
    p = Path(item.path)
    name = p.name.lower()
    age = item.last_modified_days
    size_gb = item.size_bytes / (1024**3)

    # Risiko
    if item.secret_risk or item.legal_privacy_risk:
        item.risk_score = 8
    elif item.systemd_refs or item.cron_refs:
        item.risk_score = 6
    elif size_gb > 10:
        item.risk_score = 4
    else:
        item.risk_score = 2

    # Geschäftswert Heuristiken
    if any(k in name for k in ("trading", "revenue", "sales", "content", "x_", "newsletter", "crm", "client", "gpe-core")):
        item.business_value = 7
    elif any(k in name for k in ("skill", "plugin", "sensor", "worker", "hecate")):
        item.business_value = 6
    else:
        item.business_value = 3

    # Systemwert
    if name in ("loop-master", "hecate", "vault") or "paper-mcp" in name:
        item.system_value = 9
    elif "skill" in name or "plugin" in name or "sensor" in name:
        item.system_value = 7
    elif item.git_status == "clean" and item.has_tests:
        item.system_value = 6
    else:
        item.system_value = 3

    # Integrationspotenzial
    if "paper-mcp" in name or "blackhole" in name or "graph" in name or "risk_gate" in name:
        item.integration_potential = 9
    elif item.has_tests and item.has_readme and item.git_status != "no_git":
        item.integration_potential = 7
    else:
        item.integration_potential = 4

    # Löschbarkeit
    if item.systemd_refs or item.cron_refs or item.git_status == "dirty":
        item.deletability = 1
    elif age < 7 or "hecate" in name or "loop-master" in name:
        item.deletability = 1
    elif "deprecated" in name or "_archive" in name or "old" in name:
        item.deletability = 8
    elif age > 90 and not item.systemd_refs and not item.cron_refs and size_gb > 0.5:
        item.deletability = 7
    else:
        item.deletability = 4

    # 100X Impact
    item.impact_100x = min(10, max(1,
        (item.system_value + item.business_value + item.integration_potential) // 3
        - item.risk_score // 3
        + item.deletability // 4
    ))

    # Decision Class
    if item.risk_score >= 7:
        item.decision_class = "NEEDS_HUMAN_CONTEXT"
    elif item.system_value >= 8:
        item.decision_class = "KEEP_ACTIVE"
    elif item.integration_potential >= 8:
        item.decision_class = "INTEGRATE_INTO_HECATE"
    elif item.deletability >= 7 and item.business_value <= 3:
        item.decision_class = "DELETE_CANDIDATE"
    elif age > 90 and item.business_value <= 4:
        item.decision_class = "ARCHIVE_COLD"
    elif not item.has_readme and not item.has_tests and age > 60:
        item.decision_class = "DELETE_CANDIDATE"
    else:
        item.decision_class = "KEEP_REFERENCE"

    item.recommended_action = item.decision_class.replace("_", " ").lower()
    item.next_safe_step = "Decision Card review" if item.risk_score >= 5 else "Dokumentation prüfen"
    return item


def _scan_path(path: Path, item_type: str) -> DiscoveredItem | None:
    if not path.exists() or not _is_in_trust_boundary(path):
        return None
    if SENSITIVE_NAME_RE.search(str(path)):
        return None

    item = DiscoveredItem(
        id=f"disc_{path.name[:40]}_{int(time.time())}_{hash(str(path)) & 0xFFFF:04x}",
        path=str(path),
        item_type=item_type,
        size_bytes=_dir_size(path) if path.is_dir() else path.stat().st_size,
        last_modified_days=_age_days(path),
    )
    item.git_status = _git_status(path) if path.is_dir() else "no_git"
    item.languages = _detect_languages(path) if path.is_dir() else []
    item.entrypoints = _find_entrypoints(path) if path.is_dir() else []
    item.has_readme = (path / "README.md").exists() or (path / "README").exists()
    item.has_tests = _has_tests(path)
    item.has_docker = _has_docker_refs(path)
    item.systemd_refs = _related_systemd_services(path.name) if path.is_dir() else []
    item.cron_refs = _related_crons(path.name) if path.is_dir() else []
    item.secret_risk = any(k in str(path).lower() for k in ("secret", "token", "key", "env"))
    item.legal_privacy_risk = any(k in str(path).lower() for k in ("legal", "client", "kunde", "customer", "patient", "battlebook"))

    return _classify_and_score(item)


def _scan_dirs() -> list[DiscoveredItem]:
    items: list[DiscoveredItem] = []

    scan_specs: list[tuple[Path, str]] = [
        (Path("/root/projects"), "repo/project"),
        (Path("/root/vault"), "knowledge"),
        (Path("/root/opt_legacy"), "opt"),
        (Path("/opt"), "opt"),
        (Path("/root/_backups"), "backup"),
        (Path("/root/_archive"), "archive"),
        (Path("/root/tmp_legacy"), "tmp"),
    ]

    for base, itype in scan_specs:
        if not base.exists() or not _is_in_trust_boundary(base):
            continue
        for child in base.iterdir():
            if not _is_in_trust_boundary(child):
                continue
            if child.name in ("loop-master",):
                continue
            if SENSITIVE_NAME_RE.search(child.name):
                continue
            item = _scan_path(child, itype)
            if item:
                items.append(item)

    # Top-level /root items > 100 MB
    for child in Path("/root").iterdir():
        if child.is_dir() and child.name in ("projects", "vault", "opt_legacy", "tmp_legacy", "_backups", "_archive"):
            continue
        if not _is_in_trust_boundary(child):
            continue
        if not child.exists():
            continue
        try:
            size = _dir_size(child) if child.is_dir() else child.stat().st_size
        except (FileNotFoundError, OSError):
            continue
        if size < 100 * 1024**2:
            continue
        item = _scan_path(child, "large_dir")
        if item:
            items.append(item)

    return items


def _scan_system_services() -> list[DiscoveredItem]:
    items = []
    rc, out, _ = _run(["systemctl", "list-unit-files", "--type=service", "--state=enabled", "--no-pager"], timeout=20)
    if rc == 0:
        for line in out.splitlines()[:100]:
            line = line.strip()
            if not line or ".service" not in line:
                continue
            svc = line.split()[0]
            items.append(DiscoveredItem(
                id=f"disc_svc_{svc}_{int(time.time())}",
                path=f"/etc/systemd/system/{svc}",
                item_type="service",
                systemd_refs=[svc],
                risk_score=4,
                business_value=5,
                system_value=7,
                integration_potential=5,
                deletability=1,
                impact_100x=5,
                decision_class="KEEP_REFERENCE",
                recommended_action="dokumentieren und bei obsolete markieren",
                next_safe_step="in HECATE Service-Atlas aufnehmen",
            ))
    return items


def _scan_crons() -> list[DiscoveredItem]:
    items = []
    cron_dir = Path("/etc/cron.d")
    if cron_dir.exists():
        for f in cron_dir.iterdir():
            if f.is_file():
                try:
                    text = f.read_text(errors="replace")
                except Exception:
                    continue
                # Strip secret lines and detect if any active line remains
                safe_lines = [line for line in text.splitlines() if not SENSITIVE_NAME_RE.search(line)]
                active = any(not line.strip().startswith("#") and line.strip() for line in safe_lines)
                items.append(DiscoveredItem(
                    id=f"disc_cron_{f.name}_{int(time.time())}",
                    path=str(f),
                    item_type="cron",
                    cron_refs=[str(f)],
                    risk_score=3,
                    business_value=4,
                    system_value=6,
                    integration_potential=5,
                    deletability=2 if active else 5,
                    impact_100x=5,
                    decision_class="KEEP_REFERENCE",
                    recommended_action="auf Zielpfad prüfen",
                    next_safe_step="in HECATE Cron-Atlas aufnehmen",
                ))
    return items


def _docker_inventory() -> list[DiscoveredItem]:
    items = []
    rc, out, _ = _run(["docker", "ps", "--format", "{{json .}}"], timeout=15)
    if rc == 0:
        for line in out.splitlines()[:50]:
            try:
                c = json.loads(line)
                items.append(DiscoveredItem(
                    id=f"disc_docker_{c.get('Names','?')}_{int(time.time())}",
                    path=f"docker://{c.get('Names','?')}",
                    item_type="docker_container",
                    related_ports=[int(p.split('/')[0]) for p in c.get("Ports", "").split(", ") if p.split('/')[0].isdigit()][:5],
                    risk_score=3,
                    business_value=5,
                    system_value=6,
                    integration_potential=4,
                    deletability=1,
                    impact_100x=4,
                    decision_class="KEEP_REFERENCE",
                    recommended_action="dokumentieren",
                    next_safe_step="in HECATE Docker-Atlas aufnehmen",
                ))
            except Exception:
                continue
    return items


def _create_decision_card(item: DiscoveredItem) -> Path:
    DECISION_DIR.mkdir(parents=True, exist_ok=True)
    path = DECISION_DIR / f"{item.id}.md"
    size_str = f"{item.size_bytes / 1024**3:.2f} GB" if item.size_bytes >= 1024**3 else f"{item.size_bytes / 1024**2:.1f} MB"
    body = f"""# DECISION CARD

## ID
`{item.id}`

## Kategorie
{item.decision_class}

## Risk-Level
L{item.risk_score // 2 + 1}

## 100X-Impact-Score
{item.impact_100x}

## Titel
{item.path} ({item.item_type})

## Was wurde gefunden
Pfad `{item.path}` vom Typ `{item.item_type}`. Grösse: {size_str}. Alter: {item.last_modified_days:.1f} Tage.

## Warum ist das wichtig
Systemwert {item.system_value}/10, Businesswert {item.business_value}/10, Integrationspotenzial {item.integration_potential}/10, Löschbarkeit {item.deletability}/10.

## Beweise / Fundstellen
- Git-Status: {item.git_status}
- README: {'ja' if item.has_readme else 'nein'}
- Tests: {'ja' if item.has_tests else 'nein'}
- Docker: {'ja' if item.has_docker else 'nein'}
- Sprachen: {', '.join(item.languages) if item.languages else 'unbekannt'}
- Entrypoints: {', '.join(item.entrypoints) if item.entrypoints else 'keine'}
- Services: {', '.join(item.systemd_refs) if item.systemd_refs else 'keine'}
- Crons: {', '.join(item.cron_refs) if item.cron_refs else 'keine'}

## Systemzusammenhang
Hetzner-Server, ggf. verbunden mit Services/Crons/Docker.

## Option A
{item.decision_class.replace('_', ' ')}: {item.recommended_action}

## Option B
Als Referenz archivieren/erwähnen, aber nicht aktiv verändern.

## Option C
Ignorieren / auf später verschieben.

## Empfehlung
{item.recommended_action}

## Risiko
{item.risk_score}/10 Risiko; {item.systemd_refs or item.cron_refs and 'aktive Service/Cron-Referenzen vorhanden' or 'keine aktiven Referenzen'}.

## Nichtstun-Risiko
{item.decision_class == 'DELETE_CANDIDATE' and 'Speicherplatz bleibt blockiert; Bloat wächst.' or 'Wissen bleibt ungenutzt oder Risiko unerkannt.'}

## Rollback
Je nach gewählter Option: Status zurücksetzen, Archiv rückgängig machen oder aus Backup wiederherstellen.

## Betroffene Dateien / Ordner / Services / Crons / Repos
{item.path}

## Exakte geplante Schritte
1. {item.next_safe_step}
2. Bei GO: Aktion durch safety.harness ausführen
3. Verifier prüft Ergebnis
4. Ledger-Eintrag schreiben

## Verifikation
Pfad existiert / existiert nicht wie geplant; Service/Cron-Status konsistent.

## Erfolgskriterium
Entscheidung ist umgesetzt und im Ledger vermerkt.

## Antwortoptionen
- [ ] GO
- [ ] NO
- [ ] DETAILS
- [ ] PLAN ONLY
- [ ] DEFER

## Genehmigt
- **Status:** vorgeschlagen
- **Genehmigt von:**
- **Genehmigt am:**
"""
    path.write_text(body, encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)
    LEDGER = Ledger()
    rid = LEDGER.start("legacy_discovery", note="Total Legacy Discovery Hetzner read-only")

    items: list[DiscoveredItem] = []
    items.extend(_scan_dirs())
    items.extend(_scan_system_services())
    items.extend(_scan_crons())
    items.extend(_docker_inventory())

    # Sort by impact desc
    items.sort(key=lambda x: x.impact_100x, reverse=True)

    inventory = {
        "ts": _now(),
        "total": len(items),
        "by_class": {},
        "items": [asdict(i) for i in items],
    }
    for i in items:
        inventory["by_class"][i.decision_class] = inventory["by_class"].get(i.decision_class, 0) + 1

    INVENTORY_PATH.write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")

    cards: list[Path] = []
    for item in items[:20]:
        cards.append(_create_decision_card(item))

    digest_path = Path("/root/projects/loop-master/reports/legacy_discovery_digest.md")
    lines = [
        f"# HECATE Legacy Discovery Digest — {_now()}",
        "",
        f"Gefundene Items: {len(items)}",
        f"Decision Cards erzeugt: {len(cards)}",
        "",
        "## Verteilung nach Entscheidungsklasse",
    ]
    for cls, count in sorted(inventory["by_class"].items(), key=lambda x: x[1], reverse=True):
        lines.append(f"- {cls}: {count}")
    lines.append("")
    lines.append("## Top 10 nach 100X-Impact")
    for i in items[:10]:
        size = i.size_bytes / 1024**3
        lines.append(f"- `{i.path}` | {i.decision_class} | Impact {i.impact_100x}/10 | {size:.2f} GB | {i.risk_score}/10 Risiko")
    digest_path.write_text("\n".join(lines), encoding="utf-8")

    LEDGER.finish(rid, output_path=str(digest_path))
    return {
        "items": len(items),
        "cards": len(cards),
        "inventory": str(INVENTORY_PATH),
        "digest": str(digest_path),
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, ensure_ascii=False))
