#!/usr/bin/env python3
"""Session Memory Bridge — Jarvis erinnert sich an vorherige Sessions.

Speichert Session-Zusammenfassungen, damit der Agent beim nächsten Start
sofort Kontext hat.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

STORE = Path("/var/lib/loop-master/agent_memory/sessions.jsonl")
STORE.parent.mkdir(parents=True, exist_ok=True)

def save_session(summary: str, topics: list[str], decisions: list[dict]):
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "summary": summary[:500],
        "topics": topics,
        "decisions": decisions,
    }
    with open(STORE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def get_last_sessions(n: int = 3) -> list:
    if not STORE.exists(): return []
    sessions = [json.loads(l) for l in open(STORE) if l.strip()]
    return sessions[-n:]

def get_context_for_new_session() -> str:
    sessions = get_last_sessions(3)
    if not sessions:
        return "Keine vorherigen Sessions."
    lines = ["## Letzte Sessions"]
    for s in sessions:
        lines.append(f"- {s['ts'][:10]}: {s['summary'][:80]}")
        for d in s.get("decisions", []):
            lines.append(f"  → {d['topic']}: {d['decision']}")
    return "\n".join(lines)

if __name__ == "__main__":
    print(get_context_for_new_session())
