#!/usr/bin/env python3
"""Trend Analyzer — historische Daten auswerten."""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

BUS = Path("/var/lib/loop-master/findings.jsonl")
DISK_TREND = Path("/var/lib/loop-master/disk_trend.jsonl")

def analyze_findings_trend(hours=24):
    if not BUS.exists(): return {}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    counts = {"krit":0,"hoch":0,"mittel":0,"info":0}
    sensors = {}
    for line in open(BUS):
        if not line.strip(): continue
        f = json.loads(line)
        try:
            ts = datetime.fromisoformat(f.get("ts",""))
        except: continue
        if ts > cutoff:
            sev = f.get("severity","info")
            counts[sev] = counts.get(sev,0)+1
            sensors[f.get("sensor","unknown")] = sensors.get(f.get("sensor","unknown"),0)+1
    return {"period_hours":hours,"counts":counts,"top_sensors":sorted(sensors.items(),key=lambda x:x[1],reverse=True)[:5],"trend":"rising" if counts["krit"]+counts["hoch"] > 5 else "stable"}

def analyze_disk_trend():
    if not DISK_TREND.exists(): return {}
    samples = [json.loads(l) for l in open(DISK_TREND) if l.strip()]
    if len(samples) < 2: return {"samples":len(samples)}
    recent = samples[-50:]
    xs = list(range(len(recent)))
    ys = [s.get("used_pct",0) for s in recent]
    n=len(xs); sum_x=sum(xs); sum_y=sum(ys); sum_xy=sum(x*y for x,y in zip(xs,ys)); sum_x2=sum(x*x for x in xs)
    try: slope=(n*sum_xy-sum_x*sum_y)/(n*sum_x2-sum_x*sum_x)
    except: slope=0
    current=ys[-1]
    return {"current_pct":current,"slope_pct_per_sample":round(slope,3),"projected_24h_pct":round(current+slope*24,1),"samples":n}

def cmd_trend():
    f=analyze_findings_trend(24)
    d=analyze_disk_trend()
    print(json.dumps({"findings":f,"disk":d},indent=2,ensure_ascii=False))

if __name__=="__main__":
    cmd_trend()
