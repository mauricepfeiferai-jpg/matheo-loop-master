#!/usr/bin/env python3
"""Hecate Bridge — MauriceAI Agent Kontext + Action Interface.

Stellt Hecate-Kontext für den MauriceAI-Agent bereit.
Autonomie-Level (in SOUL.md definiert):
    L1 (Read):  status, findings, sensors — autonom
    L2 (Routine): trigger sensor — nach GO oder bei 🔴/🟠 ohne GO wenn <30min
    L3+ (Create/Execute/Destructive): — nach GO
"""
import json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

BUS = Path("/var/lib/loop-master/findings.jsonl")
SENSORS = Path(__file__).resolve().parent / "sensors"

def read_bus(n=20):
    if not BUS.exists(): return []
    with open(BUS) as f: return [json.loads(l) for l in f if l.strip()][-n:]

def sensor_status():
    names = ["config_drift","disk_trend","restart_loops","cron_verify","secret_scan","cert_expiry","ledger_stale"]
    findings = read_bus(100)
    out = []
    for s in names:
        sf = [f for f in findings if f.get("sensor")==s]
        latest = sf[-1] if sf else None
        alert = any(f.get("severity") in ("krit","hoch") for f in sf[-5:])
        out.append({"sensor":s, "alert":alert, "latest":latest.get("subject","—") if latest else "—", "count":len(sf)})
    return out

def snapshot():
    f = read_bus(50)
    c = {"krit":0,"hoch":0,"mittel":0,"info":0}
    for x in f:
        sev = x.get("severity","info")
        if sev in c: c[sev] += 1
    return {"ts":datetime.now(timezone.utc).isoformat(),"findings":c,"sensors":sensor_status()}

def cmd_status():
    print(json.dumps(snapshot(), indent=2, ensure_ascii=False))

def cmd_findings(args):
    n = int(args[0]) if args else 5
    icons = {"krit":"🔴","hoch":"🟠","mittel":"🟡","info":"🔵"}
    for f in read_bus(n):
        sev = f.get("severity","info")
        print(f"{icons.get(sev,'⚪')} [{f.get('sensor','?')}] {f.get('subject','—')}")

def cmd_sensors():
    for s in sensor_status():
        icon = "🔴" if s["alert"] else "✅"
        print(f"{icon} {s['sensor']:20s} — {s['latest'][:50]} ({s['count']} heute)")

def cmd_trigger(args):
    if not args:
        print("Verfügbare Sensoren:")
        for s in sensor_status(): print(f"  - {s['sensor']}")
        return
    name = args[0]
    py = SENSORS / f"{name}.py"
    if not py.exists(): print(f"❌ Sensor {name} nicht gefunden"); return
    r = subprocess.run([sys.executable, str(py)], capture_output=True, text=True, timeout=60)
    print(f"exit={r.returncode}\n{r.stdout[-300:]}")

CMDS = {
    "status": cmd_status,
    "findings": lambda: cmd_findings(sys.argv[2:]),
    "sensors": cmd_sensors,
    "trigger": lambda: cmd_trigger(sys.argv[2:]),
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print("hecate_bridge.py <status|findings|sensors|trigger>")
        sys.exit(1)
    CMDS[sys.argv[1]]()
