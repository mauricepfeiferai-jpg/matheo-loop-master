#!/usr/bin/env python3
"""Agent Team Feedback — Ergebnisse zurück in Bus + Ledger.

Schließt Lücke #3: Agent-Team produziert Outputs, aber nichts konsumiert sie.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

BUS = Path("/var/lib/loop-master/findings.jsonl")

def emit_agent_finding(job_id: str, agent_type: str, status: str, result: str, output_path: str = ""):
    """Schreibt Agent-Job-Ergebnis als Finding in den Bus."""
    finding = {
        "sensor": "agent_team",
        "severity": "info" if status == "ok" else "hoch",
        "f_class": f"agent.{agent_type}.{status}",
        "subject": f"Agent-Job {job_id}",
        "evidence": result[:300],
        "suggested_fix": output_path if output_path else "",
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with open(BUS, "a") as f:
        f.write(json.dumps(finding, ensure_ascii=False) + "\n")

def emit_agent_proposal(job_id: str, agent_type: str, proposal_text: str):
    """Erzeugt ein Proposal aus Agent-Ergebnis."""
    proposals_dir = Path("/root/projects/loop-master/proposals")
    proposals_dir.mkdir(parents=True, exist_ok=True)
    slug = f"agent_{agent_type}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    path = proposals_dir / f"{slug}.md"
    body = f"""---
source: agent_team
agent: {agent_type}
job_id: {job_id}
status: vorgeschlagen
---

# Proposal aus Agent-Job

{proposal_text[:2000]}

*Erzeugt: {datetime.now(timezone.utc).isoformat()}*
"""
    path.write_text(body, encoding="utf-8")
    return str(path)
