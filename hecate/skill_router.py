#!/usr/bin/env python3
"""Skill Router — erkennt Task-Typ, lädt passenden Skill.

Mapping:
- coding → agent-code-reviewer
- security → agent-security-auditor
- sensor/config → sensor-config-drift
- sensor/secrets → sensor-secret-scan
- review → agent-code-reviewer
- audit → agent-security-auditor
"""
import re
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent / "skills"

KEYWORD_MAP = {
    "coding": "agent-code-reviewer",
    "code": "agent-code-reviewer",
    "review": "agent-code-reviewer",
    "pull request": "agent-code-reviewer",
    "security": "agent-security-auditor",
    "secret": "sensor-secret-scan",
    "token": "sensor-secret-scan",
    "config": "sensor-config-drift",
    "drift": "sensor-config-drift",
    "systemd": "sensor-config-drift",
    "cron": "sensor-config-drift",
    "audit": "agent-security-auditor",
    "vulnerability": "agent-security-auditor",
    "auth": "agent-security-auditor",
}


def detect_skill(text: str) -> str | None:
    text_lower = text.lower()
    for keyword, skill in KEYWORD_MAP.items():
        if keyword in text_lower:
            return skill
    return None


def load_skill(name: str) -> dict | None:
    path = SKILLS_DIR / name / "SKILL.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    frontmatter = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                import yaml
                frontmatter = yaml.safe_load(parts[1]) or {}
            except Exception:
                pass
            body = parts[2]
    return {
        "name": frontmatter.get("name", name),
        "description": frontmatter.get("description", ""),
        "sensor": frontmatter.get("sensor", ""),
        "body": body.strip(),
    }


def route(task_description: str) -> dict:
    skill_name = detect_skill(task_description)
    if skill_name:
        skill = load_skill(skill_name)
        if skill:
            return {"matched": True, "skill": skill_name, "skill_data": skill}
    return {"matched": False, "skill": None, "skill_data": None}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("skill_router.py '<task description>'")
        sys.exit(1)
    text = " ".join(sys.argv[1:])
    result = route(text)
    print(json.dumps(result, indent=2, ensure_ascii=False))
