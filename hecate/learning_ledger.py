#!/usr/bin/env python3
"""hecate.learning_ledger — Strukturierter Lern-Trace pro Agent-Run.

Unterschied zu hecate.ledger (ledger.db):
  ledger.db      → hat der Prozess geklappt? (Exit-Code, Output-Bytes)
  learning_ledger → was haben wir dabei GELERNT? (Urteil, Outcome, Pattern)

Promotion-Pfad:
  raw_trace → reviewed_learning → reusable_pattern → approved_playbook → enforced_policy

CLI:
  python3 -m hecate.learning_ledger record  --goal "..." --action "..." --model "..."
  python3 -m hecate.learning_ledger judge   <trace_id> --judgment freigegeben|abgelehnt|korrigiert
  python3 -m hecate.learning_ledger promote <trace_id> --to pattern|playbook|policy
  python3 -m hecate.learning_ledger report  [--status raw_trace|reviewed|pattern|playbook|policy]
  python3 -m hecate.learning_ledger stats
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

LEDGER_PATH = Path(os.environ.get("LEARNING_LEDGER_PATH", "/var/lib/loop-master/learning_ledger.jsonl"))
PLAYBOOKS_DIR = Path(os.environ.get("PLAYBOOKS_DIR", "/var/lib/loop-master/playbooks"))
BLOCKED_DIR = Path(os.environ.get("BLOCKED_DIR", "/var/lib/loop-master/blocked"))

PromotionStatus = Literal["raw_trace", "reviewed_learning", "reusable_pattern", "approved_playbook", "enforced_policy"]
HumanJudgment = Literal["freigegeben", "abgelehnt", "korrigiert", "pending"]

PROMOTION_ORDER = ["raw_trace", "reviewed_learning", "reusable_pattern", "approved_playbook", "enforced_policy"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAYBOOKS_DIR.mkdir(parents=True, exist_ok=True)
    BLOCKED_DIR.mkdir(parents=True, exist_ok=True)


def _load_all() -> list[dict]:
    if not LEDGER_PATH.exists():
        return []
    out = []
    for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _save_one(entry: dict) -> None:
    _ensure_dirs()
    with LEDGER_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _update(trace_id: str, updates: dict) -> dict | None:
    """Rewrite ledger with updated entry (append-only log, amend via full rewrite)."""
    entries = _load_all()
    found = None
    for i, e in enumerate(entries):
        if e.get("trace_id") == trace_id:
            entries[i] = {**e, **updates, "updated_at": _now()}
            found = entries[i]
            break
    if found is None:
        return None
    _ensure_dirs()
    with LEDGER_PATH.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return found


class LearningLedger:
    """Zugriffs-Schicht für den Learning Ledger."""

    def record(
        self,
        goal: str,
        agent_action: str,
        model_used: str,
        context: str = "",
        business_outcome: str = "",
        mistake_pattern: str = "",
        reusable_pattern: str = "",
        eval_scores: dict | None = None,
    ) -> str:
        """Erzeugt einen neuen raw_trace. Gibt trace_id zurück."""
        trace_id = uuid.uuid4().hex[:12]
        entry = {
            "trace_id": trace_id,
            "ts": _now(),
            "goal": goal,
            "context": context,
            "agent_action": agent_action,
            "model_used": model_used,
            "human_judgment": "pending",
            "business_outcome": business_outcome,
            "mistake_pattern": mistake_pattern,
            "reusable_pattern": reusable_pattern,
            "promotion_status": "raw_trace",
            "eval_scores": eval_scores or {},
        }
        _save_one(entry)
        return trace_id

    def judge(self, trace_id: str, judgment: HumanJudgment, note: str = "") -> dict | None:
        """Trägt menschliches Urteil ein und befördert zu reviewed_learning."""
        updates: dict = {"human_judgment": judgment, "judgment_note": note}
        if judgment in ("freigegeben", "korrigiert"):
            updates["promotion_status"] = "reviewed_learning"
        elif judgment == "abgelehnt":
            updates["promotion_status"] = "reviewed_learning"
        return _update(trace_id, updates)

    def promote(self, trace_id: str, to: PromotionStatus, author: str = "hecate") -> dict | None:
        """Befördert Trace im Promotion-Pfad. Schreibt Playbook/Policy-Datei wenn nötig."""
        entries = _load_all()
        entry = next((e for e in entries if e.get("trace_id") == trace_id), None)
        if entry is None:
            return None

        current = entry.get("promotion_status", "raw_trace")
        if PROMOTION_ORDER.index(to) <= PROMOTION_ORDER.index(current):
            return entry  # kein Rückschritt

        updated = _update(trace_id, {"promotion_status": to, "promoted_by": author})

        if to == "approved_playbook" and updated:
            self._write_playbook(updated)
        elif to == "enforced_policy" and updated:
            self._write_blocked(updated)

        return updated

    def _write_playbook(self, entry: dict) -> None:
        slug = entry["trace_id"]
        path = PLAYBOOKS_DIR / f"{slug}.json"
        playbook = {
            "trace_id": entry["trace_id"],
            "goal_pattern": entry.get("goal", ""),
            "reusable_pattern": entry.get("reusable_pattern", ""),
            "model_used": entry.get("model_used", ""),
            "promoted_at": _now(),
            "eval_scores": entry.get("eval_scores", {}),
        }
        path.write_text(json.dumps(playbook, indent=2, ensure_ascii=False))

    def _write_blocked(self, entry: dict) -> None:
        slug = entry["trace_id"]
        path = BLOCKED_DIR / f"{slug}.json"
        block = {
            "trace_id": entry["trace_id"],
            "mistake_pattern": entry.get("mistake_pattern", ""),
            "goal": entry.get("goal", ""),
            "blocked_at": _now(),
            "judgment": entry.get("human_judgment", ""),
        }
        path.write_text(json.dumps(block, indent=2, ensure_ascii=False))

    def get(self, trace_id: str) -> dict | None:
        return next((e for e in _load_all() if e.get("trace_id") == trace_id), None)

    def list(self, status: PromotionStatus | None = None) -> list[dict]:
        entries = _load_all()
        if status:
            entries = [e for e in entries if e.get("promotion_status") == status]
        return sorted(entries, key=lambda e: e.get("ts", ""), reverse=True)

    def stats(self) -> dict:
        entries = _load_all()
        counts: dict[str, int] = {}
        judgments: dict[str, int] = {}
        for e in entries:
            s = e.get("promotion_status", "raw_trace")
            counts[s] = counts.get(s, 0) + 1
            j = e.get("human_judgment", "pending")
            judgments[j] = judgments.get(j, 0) + 1
        playbook_count = len(list(PLAYBOOKS_DIR.glob("*.json")))
        blocked_count = len(list(BLOCKED_DIR.glob("*.json")))
        return {
            "total_traces": len(entries),
            "by_status": counts,
            "by_judgment": judgments,
            "playbooks": playbook_count,
            "blocked_patterns": blocked_count,
        }


def _cli() -> None:
    parser = argparse.ArgumentParser(description="HECATE Learning Ledger")
    sub = parser.add_subparsers(dest="cmd")

    r = sub.add_parser("record")
    r.add_argument("--goal", required=True)
    r.add_argument("--action", required=True)
    r.add_argument("--model", required=True)
    r.add_argument("--context", default="")
    r.add_argument("--outcome", default="")
    r.add_argument("--mistake", default="")
    r.add_argument("--pattern", default="")

    j = sub.add_parser("judge")
    j.add_argument("trace_id")
    j.add_argument("--judgment", required=True, choices=["freigegeben", "abgelehnt", "korrigiert"])
    j.add_argument("--note", default="")

    p = sub.add_parser("promote")
    p.add_argument("trace_id")
    p.add_argument("--to", required=True, choices=PROMOTION_ORDER)
    p.add_argument("--author", default="hecate")

    sub.add_parser("stats")

    rep = sub.add_parser("report")
    rep.add_argument("--status", choices=PROMOTION_ORDER, default=None)

    args = parser.parse_args()
    ll = LearningLedger()

    if args.cmd == "record":
        tid = ll.record(args.goal, args.action, args.model, args.context, args.outcome, args.mistake, args.pattern)
        print(tid)
    elif args.cmd == "judge":
        result = ll.judge(args.trace_id, args.judgment, args.note)
        print("ok" if result else "not found", file=sys.stderr if not result else sys.stdout)
        sys.exit(0 if result else 1)
    elif args.cmd == "promote":
        result = ll.promote(args.trace_id, args.to, args.author)
        print("ok" if result else "not found", file=sys.stderr if not result else sys.stdout)
        sys.exit(0 if result else 1)
    elif args.cmd == "stats":
        print(json.dumps(ll.stats(), indent=2))
    elif args.cmd == "report":
        for e in ll.list(args.status):
            marker = {"freigegeben": "✅", "abgelehnt": "❌", "korrigiert": "🔧", "pending": "⏳"}.get(
                e.get("human_judgment", "pending"), "⏳"
            )
            print(f"{marker} [{e.get('promotion_status','?'):20s}] {e.get('trace_id','')} | {e.get('goal','')[:60]}")
    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
