#!/usr/bin/env python3
"""hecate.promotion_pipeline — Automatisiert den Promotion-Pfad im Learning Ledger.

Liest raw_traces, bewertet mit eval_engine, schlägt Promotions vor.
Automatische Promotion bis reviewed_learning (nach Human-Judgment).
Ab reusable_pattern: Telegram-Tap für Maurice-Freigabe.

Promotion-Leiter:
  raw_trace
    → reviewed_learning   (Human hat geurteilt: auto wenn judgment != pending)
      → reusable_pattern  (3+ ähnliche Traces mit gleichem Urteil + Eval ≥ 0.7)
        → approved_playbook (Maurice 1-Tap via Telegram)
          → enforced_policy (Maurice 1-Tap, landet in governance/)

CLI:
  python3 -m hecate.promotion_pipeline run        # Vollständiger Promotion-Lauf
  python3 -m hecate.promotion_pipeline candidates # Zeigt Kandidaten für nächste Stufe
  python3 -m hecate.promotion_pipeline stats
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from hecate.learning_ledger import LearningLedger, PLAYBOOKS_DIR
from hecate.eval_engine import EvalEngine

GOVERNANCE_DIR = Path("/root/projects/loop-master/governance")
PATTERN_THRESHOLD = 3   # min. ähnliche Traces für reusable_pattern
EVAL_THRESHOLD = 0.7    # min. Eval-Score für Promotion


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _similarity_key(entry: dict) -> str:
    """Gruppierschlüssel für ähnliche Traces."""
    goal_words = set((entry.get("goal") or "").lower().split()[:5])
    mistake = (entry.get("mistake_pattern") or "").strip()
    pattern = (entry.get("reusable_pattern") or "").strip()[:40]
    return f"{mistake}|{pattern}|{'_'.join(sorted(goal_words))}"


class PromotionPipeline:

    def __init__(self) -> None:
        self.ll = LearningLedger()
        self.ee = EvalEngine()

    def run(self, dry_run: bool = False) -> dict:
        promoted = {"reviewed_learning": 0, "reusable_pattern": 0, "candidates_for_playbook": 0}

        # Stufe 1: raw_trace → reviewed_learning (wenn Human geurteilt hat)
        raw_traces = self.ll.list("raw_trace")
        for entry in raw_traces:
            if entry.get("human_judgment") not in ("pending", None, ""):
                if not dry_run:
                    self.ll.promote(entry["trace_id"], "reviewed_learning")
                promoted["reviewed_learning"] += 1

        # Stufe 2: reviewed_learning → reusable_pattern (3+ ähnliche, Eval ≥ 0.7)
        reviewed = self.ll.list("reviewed_learning")
        sim_groups: dict[str, list[dict]] = {}
        for entry in reviewed:
            key = _similarity_key(entry)
            sim_groups.setdefault(key, []).append(entry)

        for key, group in sim_groups.items():
            approved_in_group = [e for e in group if e.get("human_judgment") == "freigegeben"]
            if len(approved_in_group) < PATTERN_THRESHOLD:
                continue
            avg_score = self._avg_eval_score(approved_in_group)
            if avg_score < EVAL_THRESHOLD:
                continue
            for entry in approved_in_group:
                if not dry_run:
                    self.ll.promote(entry["trace_id"], "reusable_pattern", author="pipeline_auto")
            promoted["reusable_pattern"] += len(approved_in_group)

        # Stufe 3: reusable_pattern → approved_playbook (braucht Maurice-Freigabe)
        patterns = self.ll.list("reusable_pattern")
        promoted["candidates_for_playbook"] = len(patterns)

        return promoted

    def candidates(self) -> list[dict]:
        """Traces die bereit für nächste Promotion-Stufe sind."""
        result = []
        for status in ("raw_trace", "reviewed_learning", "reusable_pattern"):
            for entry in self.ll.list(status):
                next_step, reason = self._next_step(entry)
                if next_step:
                    result.append({
                        "trace_id": entry["trace_id"],
                        "current": status,
                        "next": next_step,
                        "reason": reason,
                        "goal": (entry.get("goal") or "")[:60],
                    })
        return result

    def _next_step(self, entry: dict) -> tuple[str | None, str]:
        status = entry.get("promotion_status", "raw_trace")
        judgment = entry.get("human_judgment", "pending")

        if status == "raw_trace" and judgment != "pending":
            return "reviewed_learning", "Human hat geurteilt"
        if status == "reviewed_learning" and judgment == "freigegeben":
            scores = entry.get("eval_scores", {})
            avg = sum(v for v in scores.values() if v is not None) / max(1, len([v for v in scores.values() if v is not None]))
            if avg >= EVAL_THRESHOLD:
                return "reusable_pattern", f"Eval-Score {avg:.2f} ≥ {EVAL_THRESHOLD}"
        if status == "reusable_pattern":
            return "approved_playbook", "Wartet auf Maurice-Freigabe (Telegram 1-Tap)"
        if status == "approved_playbook":
            return "enforced_policy", "Wartet auf Maurice-Bestätigung für Policy"
        return None, ""

    def _avg_eval_score(self, entries: list[dict]) -> float:
        all_scores = []
        for e in entries:
            scores = e.get("eval_scores", {})
            vals = [v for v in scores.values() if v is not None]
            if vals:
                all_scores.append(sum(vals) / len(vals))
        return sum(all_scores) / len(all_scores) if all_scores else 0.0

    def stats(self) -> dict:
        base = self.ll.stats()
        candidates = self.candidates()
        base["candidates_ready"] = len(candidates)
        base["next_actions"] = [
            f"{c['trace_id']} → {c['next']} ({c['reason']})"
            for c in candidates[:5]
        ]
        return base


def _cli() -> None:
    parser = argparse.ArgumentParser(description="HECATE Promotion Pipeline")
    sub = parser.add_subparsers(dest="cmd")

    run = sub.add_parser("run")
    run.add_argument("--dry-run", action="store_true")

    sub.add_parser("candidates")
    sub.add_parser("stats")

    args = parser.parse_args()
    pp = PromotionPipeline()

    if args.cmd == "run":
        result = pp.run(dry_run=getattr(args, "dry_run", False))
        print(json.dumps(result, indent=2))
    elif args.cmd == "candidates":
        for c in pp.candidates():
            print(f"[{c['current']:20s}] → {c['next']:20s} | {c['trace_id']} | {c['goal']}")
            print(f"  Grund: {c['reason']}")
    elif args.cmd == "stats":
        print(json.dumps(pp.stats(), indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
