"""Revenue Loop — taeglich ein Vertriebsschritt.

HECATE's 100x-Hebel: Distribution ist der Engpass.
Dieser Loop laeuft einmal taeglich und erzeugt GENAU EIN Proposal,
das einen Vertriebsschritt vorschlaegt. Kein Spam. Keine Automatisierung
ohne Freigabe.

Eingaben:
- knowledge_gold.db (vorhandenes Wissen zu Produkten/Skills)
- agent_memory/profile.json (Maurice-Profil)
- agent_memory/decisions.jsonl (fruehere NEIN/GO Entscheidungen)
- Bus-Findings (Systemgesundheit, damit Vertrieb nicht auf brennendes Haus folgt)

Ausgabe:
- Proposal in /root/projects/loop-master/proposals/revenue-daily-YYYY-MM-DD.md
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from hecate.knowledge_gold import query_gold
from hecate.memory_store import get_profile, get_decisions, should_ask
from hecate.model_route_gate import ModelRouteGate
from sensors.bus import BUS_PATH

PROPOSAL_TYPE = "revenue-daily"


def _system_health_ok(bus_path: Path = BUS_PATH) -> tuple[bool, str]:
    """Prueft, ob HECATE heute Vertrieb empfehlen sollte.

    Returns:
        (ok, begruendung)
    """
    if not bus_path.exists() or not bus_path.read_text().strip():
        return True, "keine Findings"

    krit = 0
    hoch = 0
    for line in bus_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            f = json.loads(line)
        except json.JSONDecodeError:
            continue
        if f.get("severity") == "krit":
            krit += 1
        elif f.get("severity") == "hoch":
            hoch += 1

    if krit > 0:
        return False, f"{krit} kritische Findings - Vertrieb pausiert"
    if hoch > 3:
        return False, f"{hoch} hoch-severe Findings - Vertrieb pausiert"
    return True, "System stabil"


def _collect_context() -> dict:
    """Sammelt relevanten Kontext fuer den Revenue-Schritt."""
    profile = get_profile()
    decisions = get_decisions(topic="revenue", n=10)

    # Gold-Wissen zu relevanten Themen
    gold_topics = ["KI", "Automatisierung", "BMA", "Vertrieb", "Agent", "Content"]
    gold_hits = []
    seen = set()
    for topic in gold_topics:
        for hit in query_gold(topic=topic, limit=3):
            if hit["id"] not in seen:
                seen.add(hit["id"])
                gold_hits.append(hit)
        if len(gold_hits) >= 10:
            break

    return {
        "profile": profile,
        "recent_revenue_decisions": decisions,
        "gold_knowledge": gold_hits[:10],
    }


def _build_prompt(ctx: dict, health_note: str) -> str:
    gold_lines = []
    for g in ctx["gold_knowledge"]:
        snippet = (g["content"].replace("\n", " "))[:120]
        gold_lines.append(f"- {g['name']} (score {g['gold_score']:.2f}): {snippet}...")

    prompt = f"""Du bist der Revenue-Strategie-Layer fuer HECATE.
Auftrag: Schlage fuer heute GENAU EINEN konkreten Vertriebsschritt vor.

Systemstatus: {health_note}

Maurice-Profil (Auszug):
- Stil: {ctx['profile'].get('style', 'kurz, direkt')}
- Reports: {ctx['profile'].get('preferences', {}).get('reports', 'kurz')}
- Sprache: {ctx['profile'].get('language', 'de')}

Vorhandenes Gold-Wissen:
{chr(10).join(gold_lines) if gold_lines else '- (keins)'}

Letzte Revenue-Entscheidungen:
{chr(10).join(f"- {d['ts'][:10]}: {d['decision']} ({d.get('reason', '')})" for d in ctx['recent_revenue_decisions']) if ctx['recent_revenue_decisions'] else '- (keine)'}

Regeln:
1. NUR EINE konkrete Aktion pro Tag.
2. Muss auf eine der Saeulen einzahlen: Vertrieb, Distribution, Partnerships, Content-Engine.
3. Vermeide Ideen, die Maurice schon abgelehnt hat.
4. Schlage keine reinen Code/Infra-Aufgaben vor.
5. Die Aktion sollte in <= 2 Stunden umsetzbar sein.

Antworte im JSON-Format:
{{
  "action": "kurze Beschreibung der Aktion",
  "channel": "X/LinkedIn/Email/Partner/...",
  "target_icp": "wer soll erreicht werden",
  "effort_hours": 0.5,
  "expected_outcome": "was soll passieren",
  "why_now": "warum passt das heute"
}}
"""
    return prompt


def _parse_json_safely(text: str) -> Optional[dict]:
    """Extrahiert JSON aus Text, falls das Modell Markdown drumherum schreibt."""
    text = text.strip()
    # Suche nach dem ersten { und letzten }
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def run() -> dict:
    """Haupt-Einstieg fuer den taeglichen Revenue-Loop."""
    health_ok, health_note = _system_health_ok(BUS_PATH)
    if not health_ok:
        return {
            "proposal_id": None,
            "status": "paused",
            "reason": health_note,
        }

    ctx = _collect_context()
    prompt = _build_prompt(ctx, health_note)

    gate = ModelRouteGate()
    result = gate.run("reason", prompt, force_local=True)

    if not result["success"]:
        return {
            "proposal_id": None,
            "status": "failed",
            "reason": result["error"],
        }

    parsed = _parse_json_safely(result["response"])
    if not parsed:
        return {
            "proposal_id": None,
            "status": "parse_failed",
            "raw_response": result["response"],
        }

    title = f"Revenue: {parsed.get('action', 'taeglicher Vertriebsschritt')}"
    body = f"""# Revenue-Daily — {datetime.now(timezone.utc).date()}

**Aktion:** {parsed.get('action', '')}
**Kanal:** {parsed.get('channel', '')}
**Ziel-ICP:** {parsed.get('target_icp', '')}
**Aufwand:** {parsed.get('effort_hours', 0)}h
**Erwartetes Ergebnis:** {parsed.get('expected_outcome', '')}
**Warum jetzt:** {parsed.get('why_now', '')}

## Kontext
- Systemstatus: {health_note}
- Verwendetes Modell: {result['decision']['model']} ({result['decision']['provider']})

## Naechster Schritt
Maurice prueft und gibt GO oder NEIN. Bei GO: Umsetzung durch HECATE/Hermes.
"""

    proposals_dir = Path("/root/projects/loop-master/proposals")
    proposals_dir.mkdir(parents=True, exist_ok=True)
    proposal_id = f"{PROPOSAL_TYPE}-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    proposal_path = proposals_dir / f"{proposal_id}.md"

    frontmatter = f"""---
status: vorgeschlagen
loop: {PROPOSAL_TYPE}
erstellt: {datetime.now(timezone.utc).isoformat()}
---
"""
    proposal_path.write_text(frontmatter + "\n" + body)


    return {
        "proposal_id": proposal_id,
        "status": "created",
        "model": result["decision"]["model"],
        "latency_ms": result["latency_ms"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] in ("created", "paused") else 1


if __name__ == "__main__":
    sys.exit(main())
