#!/usr/bin/env python3
"""Proposal Notifier — sendet Telegram-Freigabe-Anfragen fuer HECATE Proposals.

Regeln:
  - Nur EINE Nachricht pro Lauf, auch wenn 100 Proposals pending sind.
  - Maximal 5 Top-Proposals in der Nachricht; Rest wird als "+N weitere" genannt.
  - Nicht oefter als einmal alle 4h senden (ausser bei kritischem Sensor).
  - Command-basierte Freigabe, da Inline-Buttons nicht zuverlaessig funktionieren.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from hecate.hermes_adapter import send_message

PROPOSALS_DIR = Path("/root/projects/loop-master/proposals")
SENT_LOG = Path("/var/lib/loop-master/proposal_notifications.jsonl")
MIN_INTERVAL_HOURS = 4
MAX_DETAIL_ITEMS = 5


def _load_last_sent() -> datetime | None:
    if not SENT_LOG.exists():
        return None
    latest = None
    for line in open(SENT_LOG, encoding="utf-8", errors="replace"):
        if not line.strip():
            continue
        try:
            ts = datetime.fromisoformat(json.loads(line)["ts"])
            if latest is None or ts > latest:
                latest = ts
        except Exception:
            continue
    return latest


def _log_sent(proposal_ids: list[str]) -> None:
    SENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "proposal_ids": proposal_ids,
        "count": len(proposal_ids),
    }
    with open(SENT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def pending_approval_proposals() -> list[tuple[str, Path, str]]:
    out = []
    for p in sorted(PROPOSALS_DIR.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
        text = p.read_text(encoding="utf-8", errors="replace")
        status = "vorgeschlagen"
        m = re.search(r'status:\s*(\w+)', text)
        if m:
            status = m.group(1)
        if status == "telegram_approval":
            out.append((p.stem, p, text))
    return out


def _extract_field(text: str, label: str) -> str:
    m = re.search(rf'\*\*{re.escape(label)}:\*\*\s*([^\n]+)', text)
    if m:
        return m.group(1).strip()
    return "?"


def notify_pending(force: bool = False) -> list[str]:
    pending = pending_approval_proposals()
    if not pending:
        return []

    last = _load_last_sent()
    if not force and last and (datetime.now(timezone.utc) - last) < timedelta(hours=MIN_INTERVAL_HOURS):
        return []

    pending_sorted = sorted(pending, key=lambda x: _extract_field(x[2], "Grösse"), reverse=True)
    top = pending_sorted[:MAX_DETAIL_ITEMS]
    rest_count = len(pending_sorted) - len(top)

    lines = [
        f"🌑 HECATE Freigabe nötig — {len(pending)} Proposal(s)",
        "",
        "Top {len(top)} nach Grösse:",
    ]
    for proposal_id, _path, text in top:
        category = _extract_field(text, "Kategorie")
        size = _extract_field(text, "Grösse")
        reason = _extract_field(text, "Begründung")
        action = _extract_field(text, "Vorschlag des lokalen Classifiers")
        lines.append(
            f"• <b>{proposal_id}</b>\n"
            f"  {category} | {size} | {action}\n"
            f"  Grund: {reason[:80]}"
        )

    if rest_count > 0:
        lines.append(f"\n… und {rest_count} weitere Proposals.")

    lines.extend([
        "",
        "Befehle:",
        f"/approve-all — ALLE {len(pending)} freigeben (bitte erst prüfen!)",
        "/deny-all — ALLE ablehnen",
        "/skip-all — heute nicht erinnern",
        "Oder einzeln: /approve <proposal-id> | /deny <proposal-id>",
    ])

    msg = "\n".join(lines)
    try:
        r = send_message("telegram", msg, quiet=True)
        if r.ok:
            ids = [p[0] for p in pending]
            _log_sent(ids)
            return ids
    except Exception as exc:
        return []
    return []


def mark_all(status: str) -> list[str]:
    """Hilfsfunktion fuer /approve-all, /deny-all."""
    changed = []
    for proposal_id, path, text in pending_approval_proposals():
        new_text = re.sub(r'status:\s*\w+', f'status: {status}', text)
        path.write_text(new_text, encoding="utf-8")
        changed.append(proposal_id)
    return changed


if __name__ == "__main__":
    ids = notify_pending()
    print(f"Notified: {len(ids)} proposals")
