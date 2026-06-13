#!/usr/bin/env python3
"""Vision Engine — HECATE denkt ueber sich selbst nach und erzeugt Vision-Proposals.

Liest eigenen Zustand (Findings, Ledger, Proposals, Reports) und nutzt den
lokalen Reasoning-Router, um Verbesserungsvorschlaege zu entwickeln.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from hecate.discussion_memory import DiscussionMemory
from hecate.loop_factory import create_proposal
from hecate.reasoning_router import ReasoningRouter, TaskType

BUS = Path("/var/lib/loop-master/findings.jsonl")
REPORTS_DIR = Path("/root/projects/loop-master/reports")
PROPOSALS_DIR = Path("/root/projects/loop-master/proposals")


class VisionEngine:
    """Erzeugt Vision-Proposals aus HECATEs Selbstwahrnehmung."""

    def __init__(self, router: ReasoningRouter | None = None, memory: DiscussionMemory | None = None):
        self.router = router or ReasoningRouter()
        self.memory = memory or DiscussionMemory()

    def _read_recent_findings(self, n: int = 50) -> list[dict]:
        if not BUS.exists():
            return []
        lines = [l.strip() for l in open(BUS) if l.strip()]
        out = []
        for line in lines[-n:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def _read_recent_proposals(self, n: int = 20) -> list[dict]:
        out = []
        for p in sorted(PROPOSALS_DIR.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)[:n]:
            text = p.read_text(encoding="utf-8", errors="replace")
            status = "vorgeschlagen"
            m = re.search(r'status:\s*(\w+)', text)
            if m:
                status = m.group(1)
            out.append({"name": p.name, "status": status, "text": text[:800]})
        return out

    def _read_reports(self, n: int = 3) -> list[str]:
        if not REPORTS_DIR.exists():
            return []
        files = sorted(REPORTS_DIR.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)[:n]
        return [f.read_text(encoding="utf-8", errors="replace")[:2000] for f in files]

    def _build_state_summary(self) -> str:
        findings = self._read_recent_findings(30)
        proposals = self._read_recent_proposals(10)
        reports = self._read_reports(2)

        sev_count = {"krit": 0, "hoch": 0, "mittel": 0, "info": 0}
        for f in findings:
            sev = f.get("severity", "info")
            sev_count[sev] = sev_count.get(sev, 0) + 1

        lines = [
            "HECATE Selbstzustand:",
            f"- Findings letzte 30: {sev_count}",
            f"- Offene Proposals: {sum(1 for p in proposals if p['status'] == 'vorgeschlagen')}",
            f"- Insgesamt Proposals: {len(proposals)}",
            f"- Letzte Reports: {len(reports)}",
            "",
            "Top Findings:",
        ]
        for f in findings[-10:]:
            lines.append(f"  [{f.get('severity','?')}] {f.get('sensor','?')}: {f.get('subject','—')[:80]}")

        if proposals:
            lines.append("\nLetzte Proposals:")
            for p in proposals[:5]:
                lines.append(f"  {p['name']} ({p['status']})")

        return "\n".join(lines)

    def generate_vision(self, topic: str | None = None) -> dict:
        """Erzeugt eine Vision und speichert sie als Proposal."""
        topic = topic or "Wie kann HECATE sich selbst weiterentwickeln und besser entscheiden?"
        context = self._build_state_summary()

        vision_text = self.router.vision(topic, context)

        # Reasoner liefert oft Bullet-Struktur; wir parsen grob.
        title = self._extract_section(vision_text, ["Titel", "Thema"]) or topic
        problem = self._extract_section(vision_text, ["Problem", "Ausgangslage"]) or "—"
        concept = self._extract_section(vision_text, ["Konzept", "Vision", "Loesung"]) or vision_text[:500]
        steps = self._extract_section(vision_text, ["Umsetzungsschritte", "Schritte", "Implementation"]) or "—"
        risk = self._extract_section(vision_text, ["Risiko", "Risk"]) or "mittel"
        success = self._extract_section(vision_text, ["Erfolgsmass", "Erfolg", "Messbar"]) or "—"

        proposal_id = f"hecate-vision-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

        body = f"""# HECATE Vision: {title}

## Problem
{problem}

## Konzept
{concept}

## Umsetzungsschritte
{steps}

## Risiko
{risk}

## Erfolgsmass
{success}

## Kontext (automatisch erzeugt)
{context}
"""
        # Speichern als Proposal
        path = create_proposal(
            name=proposal_id,
            purpose=f"HECATE Vision: {title}",
            schedule="einmalig",
            command=f"python3 -m hecate.vision_engine apply {proposal_id}",
        )
        # Ueberschreibe Inhalt mit ausfuehrlicher Vision
        path.write_text(body, encoding="utf-8")

        # Diskussion anlegen
        self.memory.get_or_create(proposal_id)
        self.memory.add_message(proposal_id, "hecate", vision_text[:2000])

        return {
            "proposal_id": proposal_id,
            "title": title,
            "path": str(path),
            "summary": vision_text[:400],
        }

    def _extract_section(self, text: str, headers: list[str]) -> str | None:
        for header in headers:
            # Suche nach Markdown-Header oder Fett
            for pattern in [rf"##?\s*{re.escape(header)}\s*\n", rf"\*\*{re.escape(header)}\*\*[:\s]*\n"]:
                m = re.search(pattern, text, re.IGNORECASE)
                if m:
                    start = m.end()
                    end = re.search(r"\n##?\s+|\n\*\*[A-Z]", text[start:])
                    if end:
                        return text[start:start + end.start()].strip()
                    return text[start:].strip()
        return None

    def list_topics(self) -> list[str]:
        """Vorschlag fuer Vision-Themen, die HECATE selbst entwickeln koennte."""
        return [
            "Wie kann HECATE den Telegram-Operator-Bot verbessern?",
            "Welche alten Loops sollen in HECATE integriert werden?",
            "Wie baut HECATE einen besseren lokalen Model-Router?",
            "Was ist der naechste sichere Schritt fuer die Server-Inventur?",
            "Wie kann HECATE selbst bessere Proposals schreiben?",
        ]


if __name__ == "__main__":
    engine = VisionEngine()
    if len(__import__("sys").argv) > 1:
        topic = " ".join(__import__("sys").argv[1:])
        result = engine.generate_vision(topic)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for t in engine.list_topics():
            print(t)
