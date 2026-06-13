#!/usr/bin/env python3
"""HECATE Decision Card Loop — Pilot.

Input: findings.jsonl, proposals, ledger, STATE.md
Output: decision_queue.jsonl, decision_cards/*.md, Daily Digest

Regeln:
  - Keine Dateiänderung außerhalb decision_cards/ und reports/.
  - Telegram nur bei echten Entscheidungen.
  - Jede Erfolgsmeldung hat Verifier-Beleg.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hecate.ledger import Ledger
from hecate.reasoning_router import ReasoningRouter, TaskType

BUS = Path("/var/lib/loop-master/findings.jsonl")
PROPOSALS_DIR = Path("/root/projects/loop-master/proposals")
DECISION_DIR = Path("/root/projects/loop-master/decision_cards")
QUEUE_PATH = Path("/var/lib/loop-master/decision_queue.jsonl")
REPORT_DIR = Path("/root/projects/loop-master/reports")
LEDGER = Ledger()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:8]


@dataclass
class DecisionCard:
    id: str
    category: str
    risk_level: str
    impact_score: int
    title: str
    found: str
    importance: str
    evidence: str
    system_context: str
    option_a: str
    option_b: str
    option_c: str
    recommendation: str
    risk: str
    no_action_risk: str
    rollback: str
    affected: str
    steps: str
    verification: str
    success_criteria: str
    status: str = "vorgeschlagen"


def _load_findings(limit: int = 100) -> list[dict]:
    if not BUS.exists():
        return []
    out = []
    for line in open(BUS, encoding="utf-8", errors="replace"):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out[-limit:]


def _cluster_findings(findings: list[dict]) -> dict[str, list[dict]]:
    clusters: dict[str, list[dict]] = {}
    for f in findings:
        sensor = f.get("sensor", "unknown")
        clusters.setdefault(sensor, []).append(f)
    return clusters


def _map_category(sensor: str) -> str:
    mapping = {
        "secret_scan": "RISK",
        "config_drift": "INTEGRATE_INTO_HECATE",
        "cron_verify": "DECOMMISSION",
        "restart_loops": "DECOMMISSION",
        "ledger_stale": "GOVERNANCE",
        "disk_trend": "DELETE_CANDIDATE",
        "auto_remediate": "GOVERNANCE",
        "understand": "NEEDS_HUMAN_CONTEXT",
    }
    return mapping.get(sensor, "NEEDS_HUMAN_CONTEXT")


def _map_risk_level(sensor: str, severity: str) -> str:
    if sensor in ("secret_scan", "config_drift") or severity == "krit":
        return "L5"
    if severity == "hoch":
        return "L4"
    return "L2"


def _build_card(sensor: str, items: list[dict], router: ReasoningRouter | None = None) -> DecisionCard:
    title = f"{sensor}: {len(items)} Finding(s) erfordern Entscheidung"
    evidence_lines = []
    affected = set()
    for item in items[:5]:
        evidence_lines.append(f"[{item.get('severity','?')}] {item.get('subject','-')}: {item.get('evidence','')[:120]}")
        if item.get("suggested_fix"):
            affected.add(item.get("suggested_fix").split()[0])
    evidence = "\n".join(evidence_lines)
    affected_str = ", ".join(sorted(affected)) if affected else "HECATE System"

    severity_counts = {"krit": 0, "hoch": 0, "mittel": 0, "info": 0}
    for item in items:
        sev = item.get("severity", "info")
        if sev in severity_counts:
            severity_counts[sev] += 1

    system_context = f"Sensor {sensor}, Severity-Count: {severity_counts}"

    category = _map_category(sensor)
    risk_level = _map_risk_level(sensor, max((i.get("severity") for i in items), key=lambda s: {"krit": 3, "hoch": 2, "mittel": 1, "info": 0}.get(s, 0)))

    impact = 7 if risk_level in ("L4", "L5") else 5
    if sensor in ("secret_scan", "restart_loops"):
        impact = 9

    options = {
        "RISK": ("Sofortige Risk-Card + Telegram an Maurice", "In Queue priorisieren", "Beobachten + im Tagesreport erwähnen"),
        "INTEGRATE_INTO_HECATE": ("Sensor/Fix in HECATE integrieren", "Als Proposal vormerken", "Ignorieren"),
        "DECOMMISSION": ("Cron/Service archivieren/reparieren", "Proposal erstellen", "Beobachten"),
        "DELETE_CANDIDATE": ("Löschkandidaten prüfen", "Speicher-Trend weiter beobachten", "Ignorieren"),
        "GOVERNANCE": ("Governance-Loop verbessern", "Im Tagesreport erwähnen", "Ignorieren"),
    }
    opts = options.get(category, ("Als Decision Card priorisieren", "In Tagesreport aufnehmen", "Beobachten"))

    importance = (
        f"Dieser Sensor meldet {len(items)} Befunde. Bei kritischen/hohen Severity ist schnelles Handeln nötig, "
        f"da HECATE sonst selbst blind wird oder das System Risiken ansammelt."
    )

    card_id = f"dc_{sensor}_{_short_hash(evidence)}{datetime.now(timezone.utc).strftime('%Y%m%d')}"

    return DecisionCard(
        id=card_id,
        category=category,
        risk_level=risk_level,
        impact_score=impact,
        title=title,
        found=f"{len(items)} Finding(s) aus Sensor '{sensor}' in den letzten 24h/letzten Läufen.",
        importance=importance,
        evidence=evidence,
        system_context=system_context,
        option_a=opts[0],
        option_b=opts[1],
        option_c=opts[2],
        recommendation="A) priorisieren, wenn kritisch/hoch; sonst B) in Tagesreport aufnehmen.",
        risk="Falsche Klassifikation; wichtige Befunde werden übersehen.",
        no_action_risk="Sensoren laufen ins Leere; Risiken bleiben unerkannt; HECATE verliert Vertrauen.",
        rollback="Card auf 'deferred' setzen; ursprüngliche Findings bleiben im Bus.",
        affected=affected_str,
        steps="1) Befunde bestätigen 2) Option wählen 3) Bei A: L4/L5 GO einholen 4) Umsetzen + Verifier",
        verification="Sensor zeigt nach Aktion weniger krit/hoch Befunde; Ledger-Eintrag vorhanden.",
        success_criteria="0 kritische Befunde für diesen Sensor nach Umsetzung OR Begründung im Ledger",
    )


def _render_card(card: DecisionCard) -> str:
    return f"""# DECISION CARD

## ID
`{card.id}`

## Kategorie
{card.category}

## Risk-Level
{card.risk_level}

## 100X-Impact-Score
{card.impact_score}

## Titel
{card.title}

## Was wurde gefunden
{card.found}

## Warum ist das wichtig
{card.importance}

## Beweise / Fundstellen
{card.evidence}

## Systemzusammenhang
{card.system_context}

## Option A
{card.option_a}

## Option B
{card.option_b}

## Option C
{card.option_c}

## Empfehlung
{card.recommendation}

## Risiko
{card.risk}

## Nichtstun-Risiko
{card.no_action_risk}

## Rollback
{card.rollback}

## Betroffene Dateien / Ordner / Services / Crons / Repos
{card.affected}

## Exakte geplante Schritte
{card.steps}

## Verifikation
{card.verification}

## Erfolgskriterium
{card.success_criteria}

## Antwortoptionen
- [ ] GO
- [ ] NO
- [ ] DETAILS
- [ ] PLAN ONLY
- [ ] DEFER

## Genehmigt
- **Status:** {card.status}
- **Genehmigt von:**
- **Genehmigt am:**
"""


def run() -> dict[str, Any]:
    DECISION_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rid = LEDGER.start("decision_card_loop", note="Pilot: Findings → Decision Cards")

    findings = _load_findings(200)
    clusters = _cluster_findings(findings)

    router = ReasoningRouter()
    cards: list[DecisionCard] = []
    for sensor, items in clusters.items():
        # Nur Sensoren mit krit/hoch oder wiederkehrenden info
        if not any(i.get("severity") in ("krit", "hoch") for i in items):
            continue
        card = _build_card(sensor, items, router)
        cards.append(card)
        path = DECISION_DIR / f"{card.id}.md"
        path.write_text(_render_card(card), encoding="utf-8")

    # Queue append
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(QUEUE_PATH, "a", encoding="utf-8") as q:
        for card in cards:
            q.write(json.dumps(asdict(card), ensure_ascii=False) + "\n")

    # Daily Digest
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    digest_path = REPORT_DIR / f"decision_digest_{today}.md"
    lines = [
        f"# HECATE Decision Digest — {today}",
        f"",
        f"Erzeugte Decision Cards: {len(cards)}",
        f"",
    ]
    for c in sorted(cards, key=lambda x: x.impact_score, reverse=True)[:10]:
        lines.append(f"- **{c.id}** | {c.category} | {c.risk_level} | Impact {c.impact_score}/10 | {c.title}")
    lines.append("")
    lines.append("Top 3 für Telegram:")
    for c in sorted(cards, key=lambda x: x.impact_score, reverse=True)[:3]:
        lines.append(f"- {c.id}: {c.title} ({c.risk_level})")
    digest_path.write_text("\n".join(lines), encoding="utf-8")

    LEDGER.finish(rid, output_path=str(digest_path))

    return {
        "cards_created": len(cards),
        "digest": str(digest_path),
        "queue": str(QUEUE_PATH),
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, ensure_ascii=False))
