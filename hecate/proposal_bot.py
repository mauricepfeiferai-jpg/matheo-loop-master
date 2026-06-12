#!/usr/bin/env python3
"""Proposal Bot — Telegram 1-Tap Freigabe.

Liest proposals/*.md, sendet als Inline-Keyboard an Telegram.
Maurice drückt ✅ → Proposal wird aktiviert.
Lücke #2: Telegram-1-Tap-Freigabe
"""
import json, os, re, subprocess
from datetime import datetime, timezone
from pathlib import Path

PROPOSALS = Path("/root/projects/loop-master/proposals")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN","")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID","")


def list_proposals():
    out = []
    for p in sorted(PROPOSALS.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        status = "vorgeschlagen"
        if "status:" in text:
            m = re.search(r'status:\s*(\w+)', text)
            if m: status = m.group(1)
        if status == "vorgeschlagen":
            out.append({"path": str(p), "name": p.name, "text": text[:500]})
    return out

def send_proposal(prop: dict):
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ KEIN TOKEN/CHAT_ID"); return False
    payload = {
        "chat_id": CHAT_ID,
        "text": f"📋 Proposal: {prop['name']}\n\n{prop['text'][:400]}\n\nFreigeben?",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "✅ GO", "callback_data": f"approve:{prop['name']}"},
                {"text": "❌ NEIN", "callback_data": f"deny:{prop['name']}"},
            ]]
        },
    }
    cmd = [
        "curl", "-s", "-X", "POST",
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        "-H", "Content-Type: application/json",
        "-d", json.dumps(payload),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        ok = json.loads(r.stdout).get("ok", False)
        return ok
    except Exception as e:
        print(f"❌ Send failed: {e}"); return False

def process_callback(data: str):
    if data.startswith("approve:"):
        name = data.replace("approve:", "")
        path = PROPOSALS / name
        if path.exists():
            text = path.read_text(encoding="utf-8")
            text = text.replace("status: vorgeschlagen", "status: genehmigt")
            text += f"\n\n*Genehmigt via Telegram: {datetime.now(timezone.utc).isoformat()}*\n"
            path.write_text(text, encoding="utf-8")
            return f"✅ {name} genehmigt"
    elif data.startswith("deny:"):
        name = data.replace("deny:", "")
        path = PROPOSALS / name
        if path.exists():
            text = path.read_text(encoding="utf-8")
            text = text.replace("status: vorgeschlagen", "status: abgelehnt")
            text += f"\n\n*Abgelehnt via Telegram: {datetime.now(timezone.utc).isoformat()}*\n"
            path.write_text(text, encoding="utf-8")
            return f"❌ {name} abgelehnt"
    return "?"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "send":
        for p in list_proposals():
            ok = send_proposal(p)
            print(f"{'✅' if ok else '❌'} {p['name']}")
    else:
        print("proposal_bot.py send")
