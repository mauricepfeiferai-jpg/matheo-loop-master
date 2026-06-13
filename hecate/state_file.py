#!/usr/bin/env python3
"""STATE.md Manager — zentrales Resume-File fuer Hecate.

Struktur (5 Sections, Polydao / Anthropic Pattern):
  1. Verified facts      — Dinge, die der Agent nicht mehr raten muss
  2. General rules       — Regeln, die ueber den konkreten Fall hinaus gelten
  3. Open failures       — Laufende Probleme (Stage 1-2)
  4. Lessons learned     — Destillierte Erkenntnisse
  5. Last session        — Resume-Pointer fuer die naechste Session

Jede Session:
  - Liest STATE.md beim Start (consult)
  - Schreibt STATE.md beim Ende (distill)

Speicherort: ~/.hecate/STATE.md
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

STATE_PATH = Path.home() / ".hecate" / "STATE.md"


@dataclass
class StateFile:
    """In-Memory Repraesentation von STATE.md."""

    verified_facts: list[str] = field(default_factory=list)
    general_rules: list[str] = field(default_factory=list)
    open_failures: list[str] = field(default_factory=list)
    lessons_learned: list[str] = field(default_factory=list)
    last_session: str = ""
    raw: str = ""

    # ── Lesen ──

    @classmethod
    def load(cls, path: Path | None = None) -> "StateFile":
        target = path or STATE_PATH
        if not target.exists():
            return cls()
        text = target.read_text(encoding="utf-8")
        return cls.parse(text)

    @classmethod
    def parse(cls, text: str) -> "StateFile":
        sections = _split_sections(text)
        return cls(
            verified_facts=_extract_bullets(sections.get("verified facts", "")),
            general_rules=_extract_bullets(sections.get("general rules", "")),
            open_failures=_extract_bullets(sections.get("open failures", "")),
            lessons_learned=_extract_bullets(sections.get("lessons learned", "")),
            last_session=sections.get("last session", "").strip(),
            raw=text,
        )

    # ── Schreiben ──

    def save(self, path: Path | None = None) -> Path:
        target = path or STATE_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        text = self.to_markdown()
        target.write_text(text, encoding="utf-8")
        return target

    def to_markdown(self) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            "# Hecate State",
            "",
            f"_Updated: {now}_",
            "",
            "## Verified facts",
            *(f"- {f}" for f in self.verified_facts),
            "",
            "## General rules",
            *(f"- {r}" for r in self.general_rules),
            "",
            "## Open failures",
            *(f"- {o}" for o in self.open_failures),
            "",
            "## Lessons learned",
            *(f"- {l}" for l in self.lessons_learned),
            "",
            "## Last session",
            self.last_session or "_(noch keine Session aufgezeichnet)_",
            "",
        ]
        return "\n".join(lines)

    # ── Mutation (immutable) ──

    def add_fact(self, fact: str) -> "StateFile":
        if fact not in self.verified_facts:
            return self.__class__(
                verified_facts=[*self.verified_facts, fact],
                general_rules=list(self.general_rules),
                open_failures=list(self.open_failures),
                lessons_learned=list(self.lessons_learned),
                last_session=self.last_session,
            )
        return self

    def add_rule(self, rule: str) -> "StateFile":
        if rule not in self.general_rules:
            return self.__class__(
                verified_facts=list(self.verified_facts),
                general_rules=[*self.general_rules, rule],
                open_failures=list(self.open_failures),
                lessons_learned=list(self.lessons_learned),
                last_session=self.last_session,
            )
        return self

    def add_lesson(self, lesson: str) -> "StateFile":
        if lesson not in self.lessons_learned:
            return self.__class__(
                verified_facts=list(self.verified_facts),
                general_rules=list(self.general_rules),
                open_failures=list(self.open_failures),
                lessons_learned=[*self.lessons_learned, lesson],
                last_session=self.last_session,
            )
        return self

    def add_open_failure(self, text: str) -> "StateFile":
        if text not in self.open_failures:
            return self.__class__(
                verified_facts=list(self.verified_facts),
                general_rules=list(self.general_rules),
                open_failures=[*self.open_failures, text],
                lessons_learned=list(self.lessons_learned),
                last_session=self.last_session,
            )
        return self

    def set_last_session(self, text: str) -> "StateFile":
        return self.__class__(
            verified_facts=list(self.verified_facts),
            general_rules=list(self.general_rules),
            open_failures=list(self.open_failures),
            lessons_learned=list(self.lessons_learned),
            last_session=text,
        )


# ─────────────────────────────────────────
# Parser-Helfer
# ─────────────────────────────────────────

_SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def _split_sections(text: str) -> dict[str, str]:
    """Splitte Markdown-Text in Sections nach ## Ueberschriften."""
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        return {}
    sections: dict[str, str] = {}
    for i, match in enumerate(matches):
        title = match.group(1).strip().lower()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[title] = text[start:end].strip()
    return sections


def _extract_bullets(section_text: str) -> list[str]:
    """Extrahiere '-' Bullet-Items aus einer Section."""
    out = []
    for line in section_text.splitlines():
        line = line.strip()
        if line.startswith("-") or line.startswith("*"):
            out.append(line[1:].strip())
    return out


# ─────────────────────────────────────────
# CLI / Demo
# ─────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hecate STATE.md Manager")
    sub = parser.add_subparsers(dest="cmd")

    p_show = sub.add_parser("show", help="Zeige aktuelles STATE.md")
    p_add = sub.add_parser("add", help="Fuege Eintrag hinzu")
    p_add.add_argument("--section", required=True, choices=["fact", "rule", "lesson", "last"])
    p_add.add_argument("--text", required=True)
    p_init = sub.add_parser("init", help="Erstelle leeres STATE.md")

    args = parser.parse_args()

    if args.cmd == "init":
        state = StateFile()
        path = state.save()
        print(f"STATE.md erstellt: {path}")
    elif args.cmd == "add":
        state = StateFile.load()
        if args.section == "fact":
            state = state.add_fact(args.text)
        elif args.section == "rule":
            state = state.add_rule(args.text)
        elif args.section == "lesson":
            state = state.add_lesson(args.text)
        elif args.section == "last":
            state = state.set_last_session(args.text)
        path = state.save()
        print(f"STATE.md aktualisiert: {path}")
    else:
        state = StateFile.load()
        print(state.to_markdown())
