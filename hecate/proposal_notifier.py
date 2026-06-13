#!/usr/bin/env python3
"""Proposal Notifier — sendet Telegram-Freigabe-Anfragen fuer HECATE Proposals.

UX-Prinzipien:
  - Nur EINE Nachricht pro Tag/Lauf.
  - Inline-Buttons (kein Command-Spam).
  - Pro Proposal: ✅ Freigeben / ❌ Ablehnen / 📄 Details / ⏭ Überspringen.
  - Gesamt: 🔥 Alle freigeben / 🚫 Alle ablehnen / 🔕 Heute Ruhe.
  - Rate-Limit: 1x alle 4h; force nur bei kritischem Sensor.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from hecate.hermes_adapter import send_message

PROPOSALS_DIR = Path("/root/projects/loop-master/proposals")


def _load_telegram_config() -> tuple[str, str]:
    """Lade Token und Chat-ID aus derselben .env wie der Telegram Operator."""
    env_path = Path("/root/.hermes/profiles/jarvis/.env")
    cfg = {}
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip().strip('"').strip("'")
    token = cfg.get("TELEGRAM_BOT_TOKEN", "")
    owner = cfg.get("TELEGRAM_ALLOWED_USERS") or cfg.get("TELEGRAM_CHAT_ID") or "8531161985"
    return token, str(owner)
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


def _log_sent(proposal_ids: list[str], method: str = "buttons") -> None:
    SENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "proposal_ids": proposal_ids,
        "count": len(proposal_ids),
        "method": method,
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


def send_message_with_markup(text: str, reply_markup: dict | None = None) -> bool:
    """Sendet Telegram-Nachricht direkt via Bot API mit Inline-Keyboard."""
    import urllib.parse
    import urllib.request

    token, chat_id = _load_telegram_config()
    if not token:
        return False

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)

    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("ok", False)
    except Exception:
        return False


def _button_rows(proposals: list[tuple[str, Path, str]]) -> list[list[dict[str, Any]]]:
    """Erzeugt Inline-Keyboard mit je 4 Buttons pro Proposal-Zeile."""
    rows = []
    for proposal_id, _path, text in proposals[:MAX_DETAIL_ITEMS]:
        size = _extract_field(text, "Grösse")
        rows.append([{"text": f"{proposal_id[:28]} ({size})", "callback_data": f"noop:{proposal_id}"}])
        rows.append([
            {"text": "✅ Freigeben", "callback_data": f"approve:{proposal_id}"},
            {"text": "❌ Ablehnen", "callback_data": f"deny:{proposal_id}"},
            {"text": "📄 Details", "callback_data": f"details:{proposal_id}"},
            {"text": "⏭ Skip", "callback_data": f"skip:{proposal_id}"},
        ])
    return rows


def _batch_buttons(total: int) -> list[dict[str, Any]]:
    return [
        {"text": f"🔥 Alle {total} freigeben", "callback_data": "approve-all"},
        {"text": f"🚫 Alle {total} ablehnen", "callback_data": "deny-all"},
        {"text": "🔕 Heute Ruhe", "callback_data": "snooze"},
    ]


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
        f"Top {len(top)} nach Grösse (neueste zuerst):",
    ]
    for proposal_id, _path, text in top:
        category = _extract_field(text, "Kategorie")
        size = _extract_field(text, "Grösse")
        action = _extract_field(text, "Vorschlag des lokalen Classifiers")
        lines.append(
            f"• <b>{proposal_id}</b>\n"
            f"  {category} | {size} | {action}"
        )
    if rest_count > 0:
        lines.append(f"\n… und {rest_count} weitere Proposals (Detail im /proposals).")

    keyboard = _button_rows(top)
    keyboard.append(_batch_buttons(len(pending)))

    msg = "\n".join(lines)
    try:
        ok = send_message_with_markup(msg, {"inline_keyboard": keyboard})
        if ok:
            ids = [p[0] for p in pending]
            _log_sent(ids, method="buttons")
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


def snooze() -> list[str]:
    """Setzt alle pending Proposals auf vorgeschlagen (kein neuer Ping heute)."""
    return mark_all("vorgeschlagen")


def set_proposal_status(proposal_id: str, status: str) -> bool:
    path = PROPOSALS_DIR / f"{proposal_id}.md"
    if not path.exists():
        matches = list(PROPOSALS_DIR.glob(f"{proposal_id}*.md"))
        if not matches:
            return False
        path = matches[0]
    text = path.read_text(encoding="utf-8", errors="replace")
    new_text = re.sub(r'status:\s*\w+', f'status: {status}', text)
    if new_text == text:
        new_text = "---\nstatus: " + status + "\n" + text.lstrip("-").lstrip()
    path.write_text(new_text, encoding="utf-8")
    return True


if __name__ == "__main__":
    ids = notify_pending()
    print(f"Notified: {len(ids)} proposals")
