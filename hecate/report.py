"""R1 — Verdichter/Reporter: Bus -> Telegram-tauglicher Kurzreport.
Deterministisch (kein LLM). SOUL-Regeln: nur krit/hoch, dedupliziert,
nie doppelt melden (reported_state), max 5 Kern-Zeilen + Zaehler.
Telegram-Versand nur wenn TELEGRAM_BOT_TOKEN+TELEGRAM_CHAT_ID als Env
gesetzt sind (root-only EnvFile) — sonst Datei-Output fuer Cron/Mensch."""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from sensors.bus import BUS_PATH
from hecate.context_compactor import compact_findings, CompactionConfig

STATE_PATH = Path("/var/lib/loop-master/reported_state.json")
REPORT_PATH = Path("/var/lib/loop-master/daily_report.md")


def _load_findings(bus_path: Path) -> list[dict]:
    if not bus_path.exists():
        return []
    out = []
    for line in bus_path.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


FRESH_WINDOW_S = 1800  # nur der letzte Sensor-Stand zaehlt als "offen" (behobene Altlast faellt raus)


def _dedup(findings: list[dict]) -> dict[tuple, dict]:
    from datetime import datetime, timedelta
    if not findings:
        return {}
    newest = max(f.get("ts", "") for f in findings)
    try:
        cutoff = (datetime.fromisoformat(newest) - timedelta(seconds=FRESH_WINDOW_S)).isoformat()
    except ValueError:
        cutoff = ""
    d: dict[tuple, dict] = {}
    for f in findings:
        if f.get("severity") in ("krit", "hoch") and f.get("ts", "") >= cutoff:
            d[(f.get("f_class"), f.get("subject"))] = f
    return d


def new_since_last(bus_path: Path = BUS_PATH, state_path: Path = STATE_PATH) -> list[dict]:
    """Nur noch nie gemeldete (f_class, subject)-Paare — Anti-Spam-Gedaechtnis."""
    current = _dedup(_load_findings(bus_path))
    seen: set[str] = set()
    if state_path.exists():
        seen = set(json.loads(state_path.read_text()))
    fresh = [f for key, f in current.items() if f"{key[0]}|{key[1]}" not in seen]
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(sorted(seen | {f"{k[0]}|{k[1]}" for k in current})))
    return fresh


def build_report(bus_path: Path = BUS_PATH) -> str:
    raw = _load_findings(bus_path)
    cfg = CompactionConfig(max_age_hours=12, max_items=10, max_chars_per_evidence=120)
    items = compact_findings(raw, cfg)
    if not items:
        return "✅ Hecate: keine offenen krit/hoch-Findings."
    lines = [f"🔁 Hecate-Report — {len(items)} offene Findings "
             f"({sum(1 for f in items if f['severity'] == 'krit')} krit)"]
    for f in items[:5]:
        marker = "🔴" if f["severity"] == "krit" else "🟠"
        evidence = f.get('evidence', '')
        lines.append(f"{marker} {f['f_class']} @ {f['subject']}: {evidence}")
    if len(items) > 5:
        lines.append(f"… +{len(items) - 5} weitere (Dashboard: python3 -m sensors.dashboard)")
    return "\n".join(lines)


def send_via_hermes(text: str, runner=None) -> bool:
    """Primaerer Versandweg: `hermes send --to telegram` (jarvis-Kanal).
    Nutzt die Gateway-Credentials von Hermes — Hecate fasst nie einen Token an."""
    import subprocess
    run = runner or (lambda cmd, inp: subprocess.run(
        cmd, input=inp, capture_output=True, text=True, timeout=30).returncode)
    try:
        return run(["hermes", "send", "--to", "telegram", "--quiet", "-f", "-"], text) == 0
    except (OSError, Exception):
        return False


def send_telegram(text: str) -> bool:
    """Versand-Kaskade: hermes send (jarvis) -> direkter API-Call (EnvFile) -> False."""
    if send_via_hermes(text):
        return True
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except OSError:
        return False


def main() -> int:
    report = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report + "\n")
    print(report)
    fresh = new_since_last()
    if fresh and any(f["severity"] == "krit" for f in fresh):
        send_telegram(build_report())  # Sofort-Ping nur bei NEUEM krit
    return 0


if __name__ == "__main__":
    sys.exit(main())
