#!/usr/bin/env python3
"""hecate.data_pipeline — Trace-Cleaning, Klassifikation, Redaktion.

Nicht jeder Log ist Wissen. Diese Pipeline entscheidet was ins Learning Ledger kommt.

Stufen:
  1. ingest  — Rohquelle lesen (findings.jsonl, Shell-Output, Telegram-Event)
  2. filter  — Rauschen entfernen (zu kurz, reine Status-Logs, Duplikate)
  3. redact  — Sensitive Daten entfernen (Keys, Tokens, Legal-Inhalte)
  4. classify — Event-Typ bestimmen (fehler, entscheidung, erfolg, noise, safety_block)
  5. emit    — Bereinigten Lernfall für learning_ledger.record() ausgeben

CLI:
  python3 -m hecate.data_pipeline process --source findings
  python3 -m hecate.data_pipeline process --source telegram_event --input '{"text": "..."}'
  python3 -m hecate.data_pipeline classify --text "Agent hat Stub erzeugt"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

BUS_PATH = Path("/var/lib/loop-master/findings.jsonl")

EventClass = Literal["fehler", "entscheidung", "erfolg", "noise", "safety_block", "unbekannt"]

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password|passwort|secret|bearer|auth)\s*[=:]\s*\S+"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"ghp_[a-zA-Z0-9]{30,}"),
    re.compile(r"xoxb-[a-zA-Z0-9\-]+"),
    re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
]

LEGAL_PATTERNS = [
    re.compile(r"(?i)\b(az\.?|aktenzeichen|klage|rechtsstreit|gericht|urteil|beschluss|6\s*ca)\b"),
]

NOISE_SIGNALS = [
    "service is running",
    "already up to date",
    "nothing to commit",
    "no changes",
    "heartbeat",
    "ping",
    "status ok",
    "alles in ordnung",
]

ERROR_SIGNALS = [
    "error", "fehler", "failed", "exception", "traceback",
    "kritisch", "krit", "crash", "abgebrochen", "timeout",
]

SUCCESS_SIGNALS = [
    "erfolgreich", "fertig", "done", "ok", "✅", "geliefert",
    "deployed", "gebaut", "erstellt", "pass",
]

DECISION_SIGNALS = [
    "freigegeben", "abgelehnt", "korrigiert", "approved", "rejected",
    "proposal", "vorschlag", "entscheidung", "gate",
]

SAFETY_SIGNALS = [
    "denied", "blocked", "verweigert", "denylist", "safety",
    "secret", "live_trading", "rm -rf", "force push",
]

MIN_TEXT_LENGTH = 30


@dataclass
class CleanedTrace:
    source: str
    raw_text: str
    cleaned_text: str
    event_class: EventClass
    has_legal: bool
    has_secret_redacted: bool
    is_noise: bool
    metadata: dict = field(default_factory=dict)

    @property
    def worth_learning(self) -> bool:
        if self.is_noise:
            return False
        if len(self.cleaned_text.strip()) < MIN_TEXT_LENGTH:
            return False
        if self.event_class == "unbekannt":
            return False
        return True


class DataPipeline:
    """Bereinigt und klassifiziert Rohdaten für das Learning Ledger."""

    def process_text(self, text: str, source: str = "unknown") -> CleanedTrace:
        has_legal = self._has_legal(text)
        redacted, has_secret = self._redact_secrets(text)
        if has_legal:
            redacted = self._redact_legal(redacted)
        event_class = self._classify(redacted)
        is_noise = self._is_noise(redacted)
        return CleanedTrace(
            source=source,
            raw_text="[redacted]" if has_secret else text,
            cleaned_text=redacted,
            event_class=event_class,
            has_legal=has_legal,
            has_secret_redacted=has_secret,
            is_noise=is_noise,
        )

    def process_finding(self, finding: dict) -> CleanedTrace:
        text = f"{finding.get('f_class', '')} {finding.get('evidence', '')} {finding.get('subject', '')}"
        trace = self.process_text(text, source=f"sensor:{finding.get('sensor', 'unknown')}")
        trace.metadata = {
            "severity": finding.get("severity", ""),
            "sensor": finding.get("sensor", ""),
            "f_class": finding.get("f_class", ""),
        }
        return trace

    def process_findings_bus(self, bus_path: Path = BUS_PATH, limit: int = 50) -> list[CleanedTrace]:
        if not bus_path.exists():
            return []
        results = []
        seen: set[str] = set()
        lines = bus_path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in reversed(lines[-200:]):
            if not line.strip():
                continue
            try:
                f = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = f"{f.get('sensor','')}:{f.get('f_class','')}:{f.get('subject','')}"
            if key in seen:
                continue
            seen.add(key)
            trace = self.process_finding(f)
            if trace.worth_learning:
                results.append(trace)
            if len(results) >= limit:
                break
        return results

    def _redact_secrets(self, text: str) -> tuple[str, bool]:
        found = False
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                found = True
                text = pattern.sub("[SECRET_REDACTED]", text)
        return text, found

    def _redact_legal(self, text: str) -> str:
        return re.sub(
            r"(?i)(az\.?\s*\S+|aktenzeichen\s*\S+)",
            "[LEGAL_REF_REDACTED]",
            text,
        )

    def _has_legal(self, text: str) -> bool:
        return any(p.search(text) for p in LEGAL_PATTERNS)

    def _classify(self, text: str) -> EventClass:
        tl = text.lower()
        if any(s in tl for s in SAFETY_SIGNALS):
            return "safety_block"
        if any(s in tl for s in DECISION_SIGNALS):
            return "entscheidung"
        if any(s in tl for s in ERROR_SIGNALS):
            return "fehler"
        if any(s in tl for s in SUCCESS_SIGNALS):
            return "erfolg"
        if any(s in tl for s in NOISE_SIGNALS):
            return "noise"
        return "unbekannt"

    def _is_noise(self, text: str) -> bool:
        tl = text.lower()
        return any(s in tl for s in NOISE_SIGNALS) or len(text.strip()) < MIN_TEXT_LENGTH


def _cli() -> None:
    parser = argparse.ArgumentParser(description="HECATE Data Pipeline")
    sub = parser.add_subparsers(dest="cmd")

    proc = sub.add_parser("process")
    proc.add_argument("--source", required=True, choices=["findings", "text", "telegram_event"])
    proc.add_argument("--input", default="", help="JSON string oder raw text")
    proc.add_argument("--limit", type=int, default=20)

    cls = sub.add_parser("classify")
    cls.add_argument("--text", required=True)

    args = parser.parse_args()
    pipeline = DataPipeline()

    if args.cmd == "classify":
        trace = pipeline.process_text(args.text, source="cli")
        print(json.dumps({
            "event_class": trace.event_class,
            "is_noise": trace.is_noise,
            "worth_learning": trace.worth_learning,
            "has_legal": trace.has_legal,
            "has_secret_redacted": trace.has_secret_redacted,
        }, indent=2))

    elif args.cmd == "process":
        if args.source == "findings":
            traces = pipeline.process_findings_bus(limit=args.limit)
            for t in traces:
                print(json.dumps({
                    "source": t.source,
                    "event_class": t.event_class,
                    "worth_learning": t.worth_learning,
                    "text": t.cleaned_text[:120],
                    "meta": t.metadata,
                }, ensure_ascii=False))
            print(f"\n→ {len(traces)} lernwürdige Events aus Bus", file=sys.stderr)
        elif args.source in ("text", "telegram_event"):
            raw = args.input or sys.stdin.read()
            try:
                data = json.loads(raw)
                text = data.get("text", raw)
            except json.JSONDecodeError:
                text = raw
            trace = pipeline.process_text(text, source=args.source)
            print(json.dumps({
                "event_class": trace.event_class,
                "worth_learning": trace.worth_learning,
                "cleaned_text": trace.cleaned_text,
                "has_legal": trace.has_legal,
                "has_secret_redacted": trace.has_secret_redacted,
            }, indent=2, ensure_ascii=False))
    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
