#!/usr/bin/env python3
"""Memory Store — Langzeitgedächtnis für MauriceAI.

Speichert:
- Profil (Präferenzen, Sprache, Kommunikationsstil)
- Projekt-Kontexte (Was läuft wo, letzter Status)
- Entscheidungs-Log ("Maurice sagte NEIN zu X am Y" → nie wieder fragen)
- Hecate-State (Letzter Snapshot, bekannte Probleme, Fixes)

Autonomie: L1-L2 (lesen/schreiben autonom), L3+ (nur mit GO)
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

STORE_DIR = Path("/var/lib/loop-master/agent_memory")
STORE_DIR.mkdir(parents=True, exist_ok=True)

PROFILE_PATH = STORE_DIR / "profile.json"
DECISIONS_PATH = STORE_DIR / "decisions.jsonl"
HECATE_STATE_PATH = STORE_DIR / "hecate_state.json"


def _load_json(path: Path, default: dict) -> dict:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default


def _save_json(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Profil ──
def get_profile() -> dict:
    return _load_json(PROFILE_PATH, {
        "language": "de",
        "style": "kurz, direkt, menschlich",
        "no_gos": [],  # Dinge die Maurice nie will
        "preferences": {
            "reports": "kurz, keine Essays",
            "alerts": "nur 🔴🟠, keine 🔵-Spam",
            "coding": "nur nach GO",
        },
    })


def update_profile(key: str, value) -> None:
    p = get_profile()
    p[key] = value
    p["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_json(PROFILE_PATH, p)


# ── Entscheidungen ──
def log_decision(topic: str, decision: str, reason: str = "") -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "topic": topic,
        "decision": decision,
        "reason": reason,
    }
    with open(DECISIONS_PATH, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_decisions(topic: str = "", n: int = 20) -> list:
    if not DECISIONS_PATH.exists():
        return []
    entries = []
    with open(DECISIONS_PATH) as f:
        for line in f:
            if line.strip():
                e = json.loads(line)
                if not topic or topic in e.get("topic", ""):
                    entries.append(e)
    return entries[-n:]


def should_ask(topic: str) -> bool:
    """Prüfe ob Maurice zu diesem Thema schon eine Entscheidung getroffen hat."""
    for d in get_decisions(topic, n=5):
        if d.get("decision") in ("nein", "no", "never", "block"):
            return False
    return True


# ── Hecate-State ──
def get_hecate_state() -> dict:
    return _load_json(HECATE_STATE_PATH, {
        "last_snapshot": {},
        "known_problems": [],
        "applied_fixes": [],
    })


def update_hecate_state(snapshot: dict, new_problems: list = None, fix: str = "") -> None:
    s = get_hecate_state()
    s["last_snapshot"] = snapshot
    s["updated_at"] = datetime.now(timezone.utc).isoformat()
    if new_problems:
        s["known_problems"].extend(new_problems)
        s["known_problems"] = s["known_problems"][-50:]  # Limit
    if fix:
        s["applied_fixes"].append({"ts": datetime.now(timezone.utc).isoformat(), "fix": fix})
        s["applied_fixes"] = s["applied_fixes"][-50:]
    _save_json(HECATE_STATE_PATH, s)


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) > 1 and sys.argv[1] == "profile":
        print(json.dumps(get_profile(), indent=2, ensure_ascii=False))
    elif len(sys.argv) > 1 and sys.argv[1] == "decisions":
        for d in get_decisions(n=10):
            print(f"{d['ts'][:10]} — {d['topic']}: {d['decision']}")
    else:
        print("memory_store.py <profile|decisions>")
