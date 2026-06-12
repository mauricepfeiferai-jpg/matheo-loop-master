"""R2 — Research-Brief-Generator: baut den Wochen-Brief fuer das Loop-Research-Team.
Deterministisch: aggregiert Bus + Ledger + Proposals zu EINEM Markdown-Brief,
der als Input fuer eine Research-Session dient (claude -p oder manuell).
Der Brief stellt die Fragen — die Research-Session liefert Antworten als
neue Proposals (via hecate.loop_factory). Kein LLM in diesem Modul."""
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sensors.bus import BUS_PATH
from hecate.loop_factory import PROPOSALS_DIR

BRIEF_PATH = Path("/var/lib/loop-master/research_brief.md")


def build_brief(bus_path: Path = BUS_PATH, proposals_dir: Path = PROPOSALS_DIR) -> str:
    findings = []
    if bus_path.exists():
        for line in bus_path.read_text().splitlines():
            if line.strip():
                try:
                    findings.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    classes = Counter(f["f_class"] for f in findings)
    open_props = sorted(p.name for p in proposals_dir.glob("*.md")) if proposals_dir.exists() else []

    lines = [
        f"# Hecate Research-Brief — {datetime.now(timezone.utc).date()}",
        "",
        "## Auftrag an die Research-Session",
        "Recherchiere (GitHub/Web/Doku) zu den unten haeufigsten Finding-Klassen und",
        "offenen Fragen. Liefere pro Empfehlung GENAU EIN Proposal via",
        "`python3 -c \"from hecate.loop_factory import create_proposal; create_proposal(...)\"`.",
        "NIEMALS direkt implementieren — Proposals durchlaufen das Freigabe-Gate.",
        "",
        "## Haeufigste Finding-Klassen (Bus)",
    ]
    for cls, n in classes.most_common(10):
        lines.append(f"- {cls}: {n} Events")
    lines += [
        "",
        "## Offene Proposals (nicht doppeln!)",
        *([f"- {p}" for p in open_props] or ["- (keine)"]),
        "",
        "## Stehende Forschungsfragen",
        "- Backoff-Patterns gegen Wiederbeleber-Konflikte (brainstem-Klasse)",
        "- Disk-Prognose besser als linear (Saisonalitaet, Log-Bursts)",
        "- Fehlende Sensor-Klassen: Docker-Health? Qdrant? Postgres? Backup-Restore-Probe?",
        "- Welche Loop-Patterns aus Hermes/Claude-Oekosystem lohnen die Uebernahme?",
        "",
        "## Leitplanken",
        "Vorschlaege muessen: reversibel sein, Ledger-instrumentiert, Harness-kompatibel,",
        "und auf das 100x-Ziel einzahlen (Revenue/Distribution > Infra-Selbstzweck).",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    brief = build_brief()
    BRIEF_PATH.parent.mkdir(parents=True, exist_ok=True)
    BRIEF_PATH.write_text(brief)
    print(brief)
    return 0


if __name__ == "__main__":
    sys.exit(main())
