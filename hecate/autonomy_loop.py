#!/usr/bin/env python3
"""HECATE Autonomy Loop — erste selbstgesteuerte Verbesserungsschleife.

Ablauf (Phase 1, deterministisch + optional lokales LLM):
  1. Liest aktuelle Decision Cards und Findings.
  2. Wählt den häufigsten Pain-Point deterministisch.
  3. Optional: lokales LLM formuliert Titel/Zusammenfassung (mit Timeout-Guard).
  4. Erzeugt Proposal + minimalen Test + Module-Skizze.
  5. Safety Harness prüft gegen Deny-List.
  6. Speichert Proposal (status: telegram_approval bei L4/L5).

Ziel: HECATE lernt aus eigenen Findings und schlägt sichere,
getestete Verbesserungen vor — ohne Cloud-Token.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hecate.ledger import Ledger
from hecate.loop_factory import create_proposal
from hecate.reasoning_router import ReasoningRouter, TaskType, ReasoningError
from safety.denylist import is_denied

BUS = Path("/var/lib/loop-master/findings.jsonl")
DECISION_DIR = Path("/root/projects/loop-master/decision_cards")
PROPOSALS_DIR = Path("/root/projects/loop-master/proposals")
LEDGER = Ledger()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_code(text: str) -> str:
    """Extrahiert Python-Code aus Markdown-Block."""
    m = re.search(r"```python\n(.*?)\n```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


def _load_top_pain_point() -> tuple[str, int, list[dict]]:
    """Deterministisch: welcher Sensor hat die meisten kritischen/hohen Findings?"""
    if not BUS.exists():
        return ("no_findings", 0, [])
    counts: dict[str, list[dict]] = {}
    for line in open(BUS, encoding="utf-8", errors="replace"):
        if not line.strip():
            continue
        try:
            f = json.loads(line)
        except Exception:
            continue
        if f.get("severity") in ("krit", "hoch"):
            counts.setdefault(f.get("sensor", "unknown"), []).append(f)
    if not counts:
        return ("no_pain", 0, [])
    top_sensor = max(counts, key=lambda k: len(counts[k]))
    return top_sensor, len(counts[top_sensor]), counts[top_sensor]


def _maybe_llm_title(sensor: str, count: int) -> tuple[str, str]:
    """Versucht, mit lokalem Modell einen Titel zu generieren; fällt zurück."""
    default_title = f"Verbesserte Handhabung von {sensor} ({count} Befunde)"
    default_summary = f"Der Sensor '{sensor}' meldet wiederholt {count} kritische/hohe Befunde. HECATE soll eine gezielte Verbesserung vorschlagen."
    try:
        router = ReasoningRouter()
        if not router.is_ollama_alive():
            return default_title, default_summary
        prompt = (
            f"HECATE Sensor '{sensor}' hat {count} kritische/hohe Findings. "
            f"Schlage EINE konkrete, sichere Verbesserung vor. Maximal 40 Worte. "
            f"Output als JSON: {{'title': '...', 'summary': '...'}}"
        )
        raw = router.generate(TaskType.REASON, prompt)
        text = _extract_code(raw) or raw
        # Suche JSON-Block
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        parsed = json.loads(text)
        return parsed.get("title", default_title), parsed.get("summary", default_summary)
    except Exception:
        return default_title, default_summary


def generate_improvement() -> dict:
    sensor, count, items = _load_top_pain_point()
    title, summary = _maybe_llm_title(sensor, count)
    proposal_id = f"hecate-autonomy-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    # Deterministischer Test-Vorschlag
    test_code = f"""def test_{sensor}_improvement_has_baseline():
    # Baseline: Sensor {sensor} sollte nach Fix weniger krit/hoch Befunde melden
    assert True  # Platzhalter: wird nach GO durch echten Test ersetzt
"""
    module_code = f"# Verbesserung fuer Sensor {sensor}: {summary[:100]}\n"

    return {
        "proposal_id": proposal_id,
        "title": title,
        "summary": summary,
        "sensor": sensor,
        "count": count,
        "test_file": f"tests/test_{sensor}_improvement.py",
        "test_code": test_code,
        "module_code": module_code,
    }


def check_safety(proposal: dict) -> dict:
    """Prüft Vorschlag gegen Deny-List."""
    combined = proposal["test_code"] + "\n" + proposal["module_code"]
    hits = []
    for line in combined.splitlines():
        reason = is_denied(line)
        if reason:
            hits.append(reason)
    return {"ok": len(hits) == 0, "hits": hits}


def store_proposal(proposal: dict) -> Path:
    path = create_proposal(
        name=proposal["proposal_id"],
        purpose=f"Autonomie-Vorschlag: {proposal['title']}",
        schedule="einmalig",
        command=f"python3 -m hecate.autonomy_loop apply {proposal['proposal_id']}",
    )
    body = path.read_text(encoding="utf-8")
    body += f"""

## Autonom erzeugte Inhalte

**Zusammenfassung:**
{proposal['summary']}

**Betroffener Sensor:** `{proposal['sensor']}` ({proposal['count']} Befunde)

**Test-Datei:** `{proposal['test_file']}`

**Test-Code:**
```python
{proposal['test_code']}
```

**Modul-Code:**
```python
{proposal['module_code']}
```

**Status:** telegram_approval
"""
    path.write_text(body, encoding="utf-8")
    return path


def run() -> dict:
    rid = LEDGER.start("hecate_autonomy_loop", note="generiert Verbesserungsvorschlag")
    proposal = generate_improvement()
    safety = check_safety(proposal)
    if not safety["ok"]:
        LEDGER.finish(rid, status="failed", note=f"deny-list hits: {safety['hits']}")
        return {"ok": False, "error": "deny-list", "hits": safety["hits"]}

    path = store_proposal(proposal)
    LEDGER.finish(rid, output_path=str(path))
    return {"ok": True, "proposal_id": proposal["proposal_id"], "path": str(path)}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "apply":
        print("apply mode: not yet implemented without GO")
        sys.exit(0)
    result = run()
    print(json.dumps(result, indent=2, ensure_ascii=False))
