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
from hecate.knowledge_gold import enrich_research_brief, sync_gold_db
from hecate.context_compactor import compact_findings, compact_proposals, CompactionConfig

BRIEF_PATH = Path("/var/lib/loop-master/research_brief.md")


def build_brief(bus_path: Path = BUS_PATH, proposals_dir: Path = PROPOSALS_DIR) -> str:
    raw_findings = []
    if bus_path.exists():
        for line in bus_path.read_text().splitlines():
            if line.strip():
                try:
                    raw_findings.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    cfg = CompactionConfig(max_age_hours=168, max_items=15, include_info=False)
    findings = compact_findings(raw_findings, cfg)
    classes = Counter(f["f_class"] for f in findings)

    prop_items = []
    if proposals_dir.exists():
        prop_items = compact_proposals(list(proposals_dir.glob("*.md")), max_per_section=10)

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
        "## Kompakte Finding-Uebersicht",
    ]
    for f in findings[:10]:
        marker = {"krit": "🔴", "hoch": "🟠", "mittel": "🟡", "info": "🔵"}.get(f["severity"], "⚪")
        lines.append(f"{marker} `{f['sensor']}` **{f['f_class']}** @ {f['subject']}: {f['evidence']}")

    lines += [
        "",
        "## Offene Proposals (nicht doppeln!)",
    ]
    if prop_items:
        for p in prop_items:
            lines.append(f"- `{p['file']}` — {p['title']}")
    else:
        lines.append("- (keine)")

    lines += [
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
    brief_lines = build_brief().splitlines()
    try:
        sync_gold_db()
        brief_lines = enrich_research_brief(brief_lines)
    except FileNotFoundError:
        pass  # Blackhole DB nicht vorhanden -> Brief ohne Gold-Sektion
    brief = "\n".join(brief_lines) + "\n"
    BRIEF_PATH.parent.mkdir(parents=True, exist_ok=True)
    BRIEF_PATH.write_text(brief)
    print(brief)
    return 0


if __name__ == "__main__":
    sys.exit(main())
