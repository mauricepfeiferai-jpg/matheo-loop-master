"""Context Compaction — reduziert Token-Last fuer Reports und Briefe.

HECATE sammelt viele kleine Findings. Werden sie roh in Prompts geladen,
entsteht Context Rot. Dieses Modul kompaktiert sie nach Regeln:

1. Deduplikation nach (f_class, subject)
2. Alters-Filter (nur relevante Fenster)
3. Severity-Priorisierung (krit > hoch > mittel > info)
4. Text-Kuerzung pro Eintrag
5. Haeufigkeits-Zusammenfassung fuer wiederholte Meldungen
6. Statische Kuerzung von langen Strings
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class CompactionConfig:
    max_age_hours: float = 24.0
    max_items: int = 20
    max_chars_per_evidence: int = 200
    include_info: bool = False
    group_by_sensor: bool = True


def _parse_ts(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _is_fresh(finding: dict, cfg: CompactionConfig) -> bool:
    ts = _parse_ts(finding.get("ts", ""))
    if ts is None:
        return True  # Kein Timestamp = behalten
    cutoff = datetime.now(timezone.utc) - timedelta(hours=cfg.max_age_hours)
    return ts >= cutoff


def _severity_rank(severity: str) -> int:
    return {"krit": 0, "hoch": 1, "mittel": 2, "info": 3}.get(severity, 4)


def _truncate(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."


def compact_findings(findings: list[dict], cfg: CompactionConfig | None = None) -> list[dict]:
    """Kompaktiert eine Liste von Findings.

    Regeln:
    - Verwirft veraltete Eintraege
    - Gruppiert nach (f_class, subject), behaelt neuestes pro Gruppe
    - Sortiert nach Severity
    - Kuerzt Evidence
    - Gibt maximal cfg.max_items zurueck
    """
    cfg = cfg or CompactionConfig()

    by_key: dict[tuple, dict] = {}
    for f in findings:
        if not _is_fresh(f, cfg):
            continue
        if not cfg.include_info and f.get("severity") == "info":
            continue
        key = (f.get("sensor"), f.get("f_class"), f.get("subject"))
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = f
        else:
            # Neuere Version behalten
            ts_new = _parse_ts(f.get("ts", ""))
            ts_old = _parse_ts(existing.get("ts", ""))
            if ts_new and ts_old and ts_new > ts_old:
                by_key[key] = f
            elif f.get("severity") in ("krit", "hoch") and existing.get("severity") not in ("krit", "hoch"):
                by_key[key] = f

    result = list(by_key.values())
    result.sort(key=lambda f: (_severity_rank(f.get("severity", "info")), f.get("ts", "")))

    compacted = []
    for f in result[: cfg.max_items]:
        compacted.append({
            "severity": f.get("severity"),
            "sensor": f.get("sensor"),
            "f_class": f.get("f_class"),
            "subject": _truncate(f.get("subject", ""), 80),
            "evidence": _truncate(f.get("evidence", ""), cfg.max_chars_per_evidence),
            "ts": f.get("ts"),
        })
    return compacted


def compact_text(text: str, max_lines: int = 50, max_chars_per_line: int = 120) -> str:
    """Kuerzt langen Text auf die wichtigsten Zeilen."""
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    kept = lines[: max_lines // 2] + ["..."] + lines[-(max_lines // 2) :]
    result = "\n".join(kept)
    if len(result) > max_lines * max_chars_per_line:
        result = result[: max_lines * max_chars_per_line - 3] + "..."
    return result


def summarize_findings(findings: list[dict], cfg: CompactionConfig | None = None) -> str:
    """Erzeugt eine Markdown-Zusammenfassung kompaktierter Findings."""
    cfg = cfg or CompactionConfig()
    compacted = compact_findings(findings, cfg)
    if not compacted:
        return "_Keine relevanten Findings im Fenster._"

    lines = [f"**{len(compacted)} relevante Findings** (letzte {cfg.max_age_hours}h)"]
    for f in compacted:
        marker = {"krit": "🔴", "hoch": "🟠", "mittel": "🟡", "info": "🔵"}.get(f["severity"], "⚪")
        lines.append(
            f"{marker} `{f['sensor']}` **{f['f_class']}** @ {f['subject']}: {f['evidence']}"
        )
    return "\n".join(lines)


def compact_proposals(proposal_paths: list[Path], max_per_section: int = 10) -> list[dict]:
    """Kompaktiert Proposal-Dateien fuer Kontext."""
    items = []
    for p in sorted(proposal_paths, key=lambda x: x.stat().st_mtime, reverse=True)[:max_per_section]:
        content = p.read_text(errors="ignore")
        title = p.name
        for line in content.splitlines()[:20]:
            if line.startswith("# "):
                title = line[2:].strip()
                break
        items.append({
            "file": p.name,
            "title": title,
            "summary": _truncate(content.replace("\n", " "), 200),
        })
    return items


def compact_for_llm(text: str, max_tokens_approx: int = 2000) -> str:
    """Generische Funktion, um Text auf ca. N Tokens zu komprimieren.

    Heuristik: 1 Token ~ 4 Zeichen.
    """
    max_chars = max_tokens_approx * 4
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def main() -> int:
    import sys
    from sensors.bus import BUS_PATH

    findings = []
    if BUS_PATH.exists():
        for line in BUS_PATH.read_text().splitlines():
            if line.strip():
                try:
                    findings.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    cfg = CompactionConfig(max_age_hours=48, max_items=10, include_info=False)
    print(summarize_findings(findings, cfg))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
