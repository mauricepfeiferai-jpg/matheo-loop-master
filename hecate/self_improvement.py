#!/usr/bin/env python3
"""Self-Improvement — Agent lernt aus Findings, aktualisiert Skills.

Liest Bus, identifiziert wiederkehrende Patterns, aktualisiert SKILL.md.
"""
import json, re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BUS = Path("/var/lib/loop-master/findings.jsonl")
SKILLS_DIR = Path(__file__).resolve().parent / "skills"

def analyze_patterns(hours=72):
    if not BUS.exists(): return []
    cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    # Simpler: last N findings
    findings = [json.loads(l) for l in open(BUS) if l.strip()][-500:]
    # Top recurring f_class
    f_classes = [f.get("f_class","") for f in findings if f.get("severity") in ("krit","hoch")]
    top = Counter(f_classes).most_common(5)
    return [{"f_class": fc, "count": c, "severity": "hoch"} for fc, c in top if fc]

def update_skill_from_pattern(skill_name: str, pattern: dict):
    path = SKILLS_DIR / skill_name / "SKILL.md"
    if not path.exists(): return False
    text = path.read_text(encoding="utf-8")
    # Append "Known Issues" section if not exists
    if "## Known Issues" not in text:
        text += "\n\n## Known Issues\n\n"
    # Check if already logged
    if pattern["f_class"] in text:
        return False
    text += f"- {pattern['f_class']}: Aufgetreten {pattern['count']}x. Prüfe vor jeder Ausführung.\n"
    path.write_text(text, encoding="utf-8")
    return True

def run():
    patterns = analyze_patterns()
    updated = 0
    for p in patterns:
        # Map f_class to skill
        if "config" in p["f_class"]:
            if update_skill_from_pattern("sensor-config-drift", p): updated += 1
        elif "secret" in p["f_class"]:
            if update_skill_from_pattern("sensor-secret-scan", p): updated += 1
        elif "agent" in p["f_class"]:
            if update_skill_from_pattern("agent-code-reviewer", p): updated += 1
    print(f"Self-Improvement: {len(patterns)} patterns, {updated} skills updated")
    return updated

if __name__ == "__main__":
    run()
