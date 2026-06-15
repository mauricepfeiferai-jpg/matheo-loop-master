#!/usr/bin/env python3
"""hecate.veteran_layer — Company Veteran Layer.

Wird VOR jedem Agent-Run aufgerufen. Sucht approved Playbooks und bekannte
Fehlerpatterns, um HECATE vor wiederholten Fehlern zu schützen und
institutionelles Wissen als Kontext-Injection bereitzustellen.

Lookup ist deterministisch (Keyword-Matching, kein LLM).

CLI:
  python3 -m hecate.veteran_layer lookup --goal "..."
  python3 -m hecate.veteran_layer blocked --action "..."
  python3 -m hecate.veteran_layer inject --goal "..." --context "..."
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

PLAYBOOKS_DIR = Path(os.environ.get("PLAYBOOKS_DIR", "/var/lib/loop-master/playbooks"))
BLOCKED_DIR = Path(os.environ.get("BLOCKED_DIR", "/var/lib/loop-master/blocked"))

_MIN_MATCH_SCORE = 1  # Mindestens 1 Keyword muss treffen


def _tokenize(text: str) -> set[str]:
    """Zerlegt Text in lowercase-Token (Wörter ≥ 3 Zeichen)."""
    import re
    return {w.lower() for w in re.split(r"[\s\-_/.,;:!?()\[\]{}\"']+", text) if len(w) >= 3}


def _match_score(query_tokens: set[str], candidate_text: str) -> int:
    """Anzahl übereinstimmender Tokens zwischen Query und Kandidat-Text."""
    candidate_tokens = _tokenize(candidate_text)
    return len(query_tokens & candidate_tokens)


def _load_json_files(directory: Path) -> list[dict]:
    if not directory.exists():
        return []
    items = []
    for p in sorted(directory.glob("*.json")):
        try:
            items.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return items


class VeteranLayer:
    """Zugriff auf approved Playbooks und bekannte Fehlerpatterns."""

    def lookup(self, goal: str, context: str = "", top_k: int = 3) -> list[dict]:
        """Sucht passende Playbooks per Keyword-Matching.

        Gibt bis zu top_k Playbooks sortiert nach Relevanz zurück.
        """
        query = goal + " " + context
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        playbooks = _load_json_files(PLAYBOOKS_DIR)
        scored = []
        for pb in playbooks:
            candidate = " ".join([
                pb.get("goal_pattern", ""),
                pb.get("reusable_pattern", ""),
                pb.get("trace_id", ""),
            ])
            score = _match_score(query_tokens, candidate)
            if score >= _MIN_MATCH_SCORE:
                scored.append((score, pb))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [pb for _, pb in scored[:top_k]]

    def lookup_blocked(self, action: str) -> list[dict]:
        """Sucht bekannte Fehlerpatterns die zur Aktion passen.

        Gibt alle matchenden Blocked-Patterns zurück (Warnsignal).
        """
        action_tokens = _tokenize(action)
        if not action_tokens:
            return []

        blocked = _load_json_files(BLOCKED_DIR)
        matches = []
        for bp in blocked:
            candidate = " ".join([
                bp.get("mistake_pattern", ""),
                bp.get("goal", ""),
            ])
            score = _match_score(action_tokens, candidate)
            if score >= _MIN_MATCH_SCORE:
                matches.append(bp)
        return matches

    def format_injection(self, playbooks: list[dict]) -> str:
        """Formatiert Playbooks als Kontext-String für Prompt-Injection."""
        if not playbooks:
            return ""
        lines = ["## HECATE Veteran Knowledge (approved playbooks)\n"]
        for pb in playbooks:
            lines.append(f"### Playbook {pb.get('trace_id', 'unknown')}")
            if pb.get("goal_pattern"):
                lines.append(f"**Ziel-Pattern:** {pb['goal_pattern']}")
            if pb.get("reusable_pattern"):
                lines.append(f"**Wiederverwendbares Muster:** {pb['reusable_pattern']}")
            lines.append("")
        return "\n".join(lines)

    def format_warnings(self, blocked: list[dict]) -> str:
        """Formatiert bekannte Fehlerpatterns als Warnung."""
        if not blocked:
            return ""
        lines = ["## ⚠️ HECATE Veteran Warning (bekannte Fehler)\n"]
        for bp in blocked:
            lines.append(f"- **Fehlerklasse:** {bp.get('mistake_pattern', 'unbekannt')}")
            if bp.get("goal"):
                lines.append(f"  Kontext: {bp['goal']}")
            if bp.get("judgment"):
                lines.append(f"  Urteil: {bp['judgment']}")
        return "\n".join(lines)

    def get_full_injection(self, goal: str, action: str = "", context: str = "") -> str:
        """Kombiniert Playbooks + Warnings zu einem vollständigen Injection-String."""
        playbooks = self.lookup(goal, context)
        blocked = self.lookup_blocked(action or goal)

        parts = []
        if playbooks:
            parts.append(self.format_injection(playbooks))
        if blocked:
            parts.append(self.format_warnings(blocked))
        return "\n".join(parts)


def _cli() -> None:
    parser = argparse.ArgumentParser(description="HECATE Veteran Layer")
    sub = parser.add_subparsers(dest="cmd")

    lu = sub.add_parser("lookup", help="Suche passende Playbooks")
    lu.add_argument("--goal", required=True)
    lu.add_argument("--context", default="")
    lu.add_argument("--top-k", type=int, default=3)

    bl = sub.add_parser("blocked", help="Suche bekannte Fehlerpatterns")
    bl.add_argument("--action", required=True)

    inj = sub.add_parser("inject", help="Vollständige Kontext-Injection")
    inj.add_argument("--goal", required=True)
    inj.add_argument("--action", default="")
    inj.add_argument("--context", default="")

    args = parser.parse_args()
    vl = VeteranLayer()

    if args.cmd == "lookup":
        results = vl.lookup(args.goal, args.context, args.top_k)
        if results:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            print("(keine passenden Playbooks gefunden)")
    elif args.cmd == "blocked":
        results = vl.lookup_blocked(args.action)
        if results:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            print("(keine bekannten Fehlerpatterns)")
    elif args.cmd == "inject":
        injection = vl.get_full_injection(args.goal, args.action, args.context)
        print(injection if injection else "(kein Veteran-Kontext verfügbar)")
    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
