"""Subagent Research — komplexe Research-Aufgaben mit Sidechain-Transkripten.

Ein Research-Subagent bekommt eine konkrete Frage, recherchiert lokal
(GitHub/Web/Doku) und schreibt sein vollstaendiges Transkript in eine
Sidechain-Datei. Zurueck an den Parent kommt nur eine 1.000-2.000 Token
Zusammenfassung plus ein Verweis auf die Sidechain.

Ziele:
- Parent-Context bleibt sauber
- Research-Ergebnisse sind reproduzierbar/auditierbar
- Token-Kosten sinken
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from hecate.model_route_gate import ModelRouteGate
from hecate.context_compactor import compact_for_llm

SIDECHAIN_DIR = Path("/var/lib/loop-master/sidechains")


def _sidechain_path(question: str) -> Path:
    """Erzeugt einen eindeutigen Dateinamen fuer das Transkript."""
    from hashlib import sha256
    h = sha256(question.encode()).hexdigest()[:12]
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return SIDECHAIN_DIR / f"research-{ts}-{h}.md"


def run_research(question: str, context: str = "") -> dict:
    """Fuehrt einen Research-Subagent-Lauf durch.

    Args:
        question: konkrete Research-Frage
        context: optionaler Hintergrund

    Returns:
        Dict mit summary, sidechain_path, model, success
    """
    SIDECHAIN_DIR.mkdir(parents=True, exist_ok=True)
    sidechain = _sidechain_path(question)

    prompt = f"""Du bist ein Research-Subagent fuer HECATE.
Auftrag: Recherchiere praezise zu der folgenden Frage.
Nutze lokales Wissen (Gold-Source, Memory, Proposals) und falls noetig GitHub/Web.
Schreibe dein komplettes Transkript in die Sidechain-Datei.
Antworte im Parent-Context NUR mit einer Zusammenfassung.

Frage: {question}

Kontext: {context or '(kein)'}

Struktur der Zusammenfassung:
- Kernbefund (3-5 Saetze)
- Top-3 Empfehlungen mit Begruendung
- Offene Risiken/Unsicherheiten
- Naechster konkreter Schritt

Zusammenfassung:"""

    gate = ModelRouteGate()
    result = gate.run("reason", prompt, force_local=True)

    if not result["success"]:
        return {
            "success": False,
            "error": result["error"],
            "sidechain_path": None,
            "summary": "",
        }

    # Sidechain-Transkript: Prompt + Response
    transcript = f"""# Research Subagent Transkript

**Frage:** {question}
**Zeit:** {datetime.now(timezone.utc).isoformat()}
**Modell:** {result['decision']['model']}

## Prompt

{prompt}

## Rohe Antwort

{result['response']}

## Zusammenfassung (Parent)

{result['response']}
"""
    sidechain.write_text(transcript, encoding="utf-8")

    summary = compact_for_llm(result["response"], max_tokens_approx=1500)

    return {
        "success": True,
        "summary": summary,
        "sidechain_path": str(sidechain),
        "model": result["decision"]["model"],
        "latency_ms": result["latency_ms"],
    }


def enrich_research_brief_with_sidechains(
    brief_lines: list[str],
    question: str = "Welche Loop-Patterns aus Hermes/Claude-Oekosystem lohnen die Uebernahme?",
) -> list[str]:
    """Erweitert einen Research-Brief um eine Subagent-Zusammenfassung."""
    result = run_research(question)
    if not result["success"]:
        return brief_lines

    insert_idx = -1
    for i, line in enumerate(brief_lines):
        if line.startswith("## Leitplanken"):
            insert_idx = i
            break

    section = [
        "",
        "## Subagent-Research (Sidechain)",
        f"**Frage:** {question}",
        f"**Modell:** {result['model']} | **Transkript:** `{result['sidechain_path']}`",
        "",
        result["summary"],
        "",
    ]

    if insert_idx >= 0:
        brief_lines = brief_lines[:insert_idx] + section + brief_lines[insert_idx:]
    else:
        brief_lines += section
    return brief_lines


def main() -> int:
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "run":
        question = sys.argv[2]
        result = run_research(question)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["success"] else 1

    print("Usage: python3 -m hecate.subagent_research run \"FRAGE\"")
    return 1


if __name__ == "__main__":
    sys.exit(main())
